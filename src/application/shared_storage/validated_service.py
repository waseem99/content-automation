from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.shared_storage.models import (
    ExistingAssetMigrationRequest,
    RestoreVerifyRequest,
    StorageQuotaRequest,
)
from src.application.shared_storage.service import (
    SharedArtifactError,
    SharedArtifactService,
    _json,
)


class ValidatedSharedArtifactService(SharedArtifactService):
    """Shared artifact service with quota, migration, and full restore verification."""

    def configure_quota(
        self,
        *,
        request: StorageQuotaRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            backend = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends WHERE id=%s FOR UPDATE",
                (request.backend_id,),
            ).fetchone()
            if not backend:
                raise SharedArtifactError("shared_backend_not_found")
            if backend["status"] not in {"active", "unavailable"}:
                raise SharedArtifactError("shared_backend_quota_not_configurable")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"shared-storage-quota:{request.backend_id}",),
            )
            current = conn.execute(
                """SELECT * FROM football_brief.shared_storage_quota_policies
                   WHERE backend_id=%s AND status='active' FOR UPDATE""",
                (request.backend_id,),
            ).fetchone()
            if current and (
                int(current["hard_limit_bytes"]) == request.hard_limit_bytes
                and int(current["warning_threshold_bytes"]) == request.warning_threshold_bytes
            ):
                return {"ok": True, **self._quota_snapshot(conn, request.backend_id), "unchanged": True}
            next_version = int(
                conn.execute(
                    """SELECT COALESCE(max(version),0)+1 AS version
                       FROM football_brief.shared_storage_quota_policies
                       WHERE backend_id=%s""",
                    (request.backend_id,),
                ).fetchone()["version"]
            )
            parent_id = None
            if current:
                parent_id = current["id"]
                conn.execute(
                    """UPDATE football_brief.shared_storage_quota_policies
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, parent_id),
                )
            conn.execute(
                """INSERT INTO football_brief.shared_storage_quota_policies
                   (backend_id,version,parent_policy_id,hard_limit_bytes,
                    warning_threshold_bytes,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,'active',%s)""",
                (
                    request.backend_id,
                    next_version,
                    parent_id,
                    request.hard_limit_bytes,
                    request.warning_threshold_bytes,
                    actor,
                ),
            )
            result = self._quota_snapshot(conn, request.backend_id)
        return {"ok": True, **result, "unchanged": False}

    def quota_status(self, *, backend_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            result = self._quota_snapshot(conn, backend_id)
        return {"ok": True, **result}

    def migrate_existing_assets(
        self,
        *,
        request: ExistingAssetMigrationRequest,
        actor: str,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for asset_id in request.asset_ids:
            try:
                shared_object = self.ensure_shared_object(
                    asset_id=asset_id,
                    backend_id=request.backend_id,
                    actor=actor,
                )
                results.append(
                    {
                        "asset_id": asset_id,
                        "ok": True,
                        "storage_object_id": shared_object["id"],
                        "sha256": shared_object["sha256"],
                        "size_bytes": shared_object["size_bytes"],
                    }
                )
            except Exception as exc:
                if not request.continue_on_error:
                    raise
                results.append(
                    {
                        "asset_id": asset_id,
                        "ok": False,
                        "error": type(exc).__name__,
                        "message": str(exc)[:500],
                    }
                )
        return {
            "ok": all(item["ok"] for item in results),
            "backend_id": request.backend_id,
            "requested": len(request.asset_ids),
            "migrated": sum(1 for item in results if item["ok"]),
            "failed": sum(1 for item in results if not item["ok"]),
            "results": results,
            "quota": self.quota_status(backend_id=request.backend_id)["quota"],
        }

    def verify_restore(
        self,
        *,
        snapshot_id: UUID,
        request: RestoreVerifyRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_active_operator(conn, actor)
            snapshot = conn.execute(
                "SELECT * FROM football_brief.shared_backup_snapshots WHERE id=%s",
                (snapshot_id,),
            ).fetchone()
            backend = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends WHERE backend_key=%s",
                (request.restored_backend_key,),
            ).fetchone()
        if not snapshot:
            raise SharedArtifactError("backup_snapshot_not_found")
        if snapshot["status"] != "prepared":
            raise SharedArtifactError("backup_snapshot_not_prepared")
        if not backend:
            raise SharedArtifactError("restored_backend_not_found")

        provider = self.providers.provider(dict(backend))
        results: list[dict[str, Any]] = []
        all_verified = True
        manifest = dict(snapshot["manifest"])
        for item in manifest.get("objects", []):
            observed_sha = None
            restored_uri = f"unavailable://{item['object_key']}"
            details: dict[str, Any] = {}
            with self.database.connection() as conn:
                current = conn.execute(
                    """SELECT sso.id,sso.asset_id,sso.object_key,sso.sha256,sso.size_bytes,sso.mime_type,
                              COALESCE(jsonb_agg(jsonb_build_object(
                                  'artifact_version_id',saor.artifact_version_id,
                                  'role',saor.role,
                                  'artifact_key',sav.artifact_key,
                                  'artifact_version',sav.version,
                                  'artifact_status',sav.status,
                                  'brand_id',sav.brand_id,
                                  'portfolio_content_id',sav.portfolio_content_id,
                                  'content_version',sav.content_version
                              ) ORDER BY sav.artifact_key,sav.version,saor.role)
                              FILTER (WHERE saor.artifact_version_id IS NOT NULL),'[]'::jsonb) AS artifact_roles
                       FROM football_brief.shared_storage_objects sso
                       LEFT JOIN football_brief.shared_artifact_object_roles saor
                         ON saor.storage_object_id=sso.id
                       LEFT JOIN football_brief.shared_artifact_versions sav
                         ON sav.id=saor.artifact_version_id
                       WHERE sso.id=%s
                       GROUP BY sso.id""",
                    (item["id"],),
                ).fetchone()
            metadata_matches = bool(
                current
                and str(current["asset_id"]) == str(item["asset_id"])
                and current["object_key"] == item["object_key"]
                and current["sha256"] == item["sha256"]
                and int(current["size_bytes"]) == int(item["size_bytes"])
                and current["mime_type"] == item["mime_type"]
                and _json(current["artifact_roles"]) == _json(item["artifact_roles"])
            )
            if not metadata_matches:
                details["metadata_mismatch"] = True
            checksum_matches = False
            try:
                verified = provider.verify(
                    object_key=item["object_key"],
                    expected_sha256=item["sha256"],
                    expected_size_bytes=int(item["size_bytes"]),
                )
                observed_sha = verified.sha256
                restored_uri = verified.storage_uri
                checksum_matches = verified.sha256 == item["sha256"]
            except Exception as exc:
                details["error"] = type(exc).__name__
                details["message"] = str(exc)[:500]

            status = "verified" if metadata_matches and checksum_matches else "failed"
            all_verified = all_verified and status == "verified"
            with self.database.transaction() as conn:
                verification = conn.execute(
                    """INSERT INTO football_brief.shared_restore_verifications
                       (snapshot_id,source_storage_object_id,restored_uri,expected_sha256,
                        observed_sha256,metadata_matches,checksum_matches,status,details,
                        verified_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                    (
                        snapshot_id,
                        item["id"],
                        restored_uri,
                        item["sha256"],
                        observed_sha,
                        metadata_matches,
                        checksum_matches,
                        status,
                        _json(details),
                        request.verifier_label,
                    ),
                ).fetchone()
            results.append(dict(verification))

        with self.database.transaction() as conn:
            final_status = "verified" if all_verified else "failed"
            timestamp_column = "verified_at" if all_verified else "failed_at"
            snapshot = conn.execute(
                f"""UPDATE football_brief.shared_backup_snapshots
                    SET status=%s,{timestamp_column}=now()
                    WHERE id=%s AND status='prepared' RETURNING *""",
                (final_status, snapshot_id),
            ).fetchone()
            if not snapshot:
                raise SharedArtifactError("backup_snapshot_state_conflict")
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,event,actor,details)
                   VALUES (%s,%s,%s,%s::jsonb)""",
                (
                    snapshot["backend_id"],
                    "restore_verified" if all_verified else "restore_failed",
                    actor,
                    _json({
                        "snapshot_id": str(snapshot_id),
                        "verification_count": len(results),
                        "metadata_and_roles_verified": all_verified,
                    }),
                ),
            )
        return {"ok": all_verified, "snapshot": dict(snapshot), "verifications": results}

    @staticmethod
    def _quota_snapshot(conn: Any, backend_id: UUID) -> dict[str, Any]:
        backend = conn.execute(
            "SELECT id,backend_key,status FROM football_brief.shared_storage_backends WHERE id=%s",
            (backend_id,),
        ).fetchone()
        if not backend:
            raise SharedArtifactError("shared_backend_not_found")
        policy = conn.execute(
            """SELECT * FROM football_brief.shared_storage_quota_policies
               WHERE backend_id=%s AND status='active'""",
            (backend_id,),
        ).fetchone()
        consumed = int(
            conn.execute(
                """SELECT COALESCE(sum(size_bytes),0) AS bytes
                   FROM football_brief.shared_storage_objects
                   WHERE backend_id=%s AND status<>'deleted'""",
                (backend_id,),
            ).fetchone()["bytes"]
        )
        quota = None
        if policy:
            hard = int(policy["hard_limit_bytes"])
            warning = int(policy["warning_threshold_bytes"])
            quota = {
                **dict(policy),
                "consumed_bytes": consumed,
                "remaining_bytes": max(0, hard - consumed),
                "warning_exceeded": consumed >= warning,
                "hard_limit_exceeded": consumed > hard,
            }
        return {"backend": dict(backend), "quota": quota, "consumed_bytes": consumed}
