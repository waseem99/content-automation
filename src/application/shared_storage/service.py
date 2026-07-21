from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from uuid import UUID

from src.application.shared_storage.models import (
    ArtifactObjectRole,
    ArtifactVersionRequest,
    BackupPrepareRequest,
    DeletionRequest,
    LegalHoldRequest,
    RestoreVerifyRequest,
    SignedAccessRequest,
    SignedAccessResult,
    StorageBackendRequest,
)
from src.application.shared_storage.providers import (
    SharedAccessTarget,
    SharedObjectHashMismatch,
    SharedObjectMissing,
    SharedStorageError,
    content_addressed_key,
    token_digest,
)
from src.application.shared_storage.runtime import (
    CanonicalAssetSourceResolver,
    SharedProviderRegistry,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class SharedArtifactError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SharedArtifactService:
    def __init__(
        self,
        database: "Database",
        *,
        providers: SharedProviderRegistry | None = None,
        source_resolver: CanonicalAssetSourceResolver | None = None,
        public_base_url: str = "",
    ) -> None:
        self.database = database
        self.providers = providers or SharedProviderRegistry()
        self.source_resolver = source_resolver or CanonicalAssetSourceResolver()
        self.public_base_url = public_base_url.rstrip("/")

    def create_backend(self, *, request: StorageBackendRequest, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """INSERT INTO football_brief.shared_storage_backends
                   (backend_key,display_name,driver,environment,status,endpoint_url,
                    bucket_name,base_prefix,region,credential_secret_ref,public_base_url,
                    configuration,created_by)
                   VALUES (%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.backend_key,
                    request.display_name,
                    request.driver.value,
                    request.environment.value,
                    request.endpoint_url,
                    request.bucket_name,
                    request.base_prefix,
                    request.region,
                    request.credential_secret_ref,
                    request.public_base_url,
                    _json(request.configuration),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,event,actor,details)
                   VALUES (%s,'backend_created',%s,%s::jsonb)""",
                (row["id"], actor, _json({"driver": row["driver"], "environment": row["environment"]})),
            )
        return {"ok": True, "backend": dict(row)}

    def activate_backend(self, *, backend_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            backend = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends WHERE id=%s FOR UPDATE",
                (backend_id,),
            ).fetchone()
            if not backend:
                raise SharedArtifactError("shared_backend_not_found")
            if backend["status"] not in {"draft", "unavailable"}:
                raise SharedArtifactError("shared_backend_not_activatable")
            existing = conn.execute(
                """SELECT id FROM football_brief.shared_storage_backends
                   WHERE environment=%s AND driver=%s AND status='active' AND id<>%s FOR UPDATE""",
                (backend["environment"], backend["driver"], backend_id),
            ).fetchone()
            if existing:
                raise SharedArtifactError(
                    "shared_backend_already_active",
                    details={"existing_backend_id": str(existing["id"])},
                )
            provider = self.providers.provider(dict(backend))
            if hasattr(provider, "ensure_ready"):
                provider.ensure_ready()  # type: ignore[attr-defined]
            activated = conn.execute(
                """UPDATE football_brief.shared_storage_backends
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, backend_id),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,event,actor,details)
                   VALUES (%s,'backend_activated',%s,'{}'::jsonb)""",
                (backend_id, actor),
            )
        return {"ok": True, "backend": dict(activated)}

    def list_backends(self) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends ORDER BY environment,driver,backend_key"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_artifact_version(
        self,
        *,
        request: ArtifactVersionRequest,
        actor: str,
    ) -> dict[str, Any]:
        asset_ids = {
            ArtifactObjectRole.ORIGINAL: request.original_asset_id,
            ArtifactObjectRole.REVIEW_PROXY: request.review_proxy_asset_id,
            ArtifactObjectRole.THUMBNAIL: request.thumbnail_asset_id,
        }
        object_rows: dict[ArtifactObjectRole, dict[str, Any]] = {}
        for role, asset_id in asset_ids.items():
            if asset_id is not None:
                object_rows[role] = self.ensure_shared_object(
                    asset_id=asset_id,
                    backend_id=request.backend_id,
                    actor=actor,
                )

        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = conn.execute(
                """SELECT * FROM football_brief.shared_artifact_versions
                   WHERE brand_id=%s AND artifact_key=%s AND status='current' FOR UPDATE""",
                (request.brand_id, request.artifact_key),
            ).fetchone()
            version = 1
            parent_id = request.parent_version_id
            if current:
                if parent_id is None:
                    parent_id = current["id"]
                if parent_id != current["id"]:
                    raise SharedArtifactError(
                        "artifact_parent_not_current",
                        details={"current_version_id": str(current["id"])},
                    )
                version = int(current["version"]) + 1
                conn.execute(
                    """UPDATE football_brief.shared_artifact_versions
                       SET status='superseded',superseded_at=now()
                       WHERE id=%s""",
                    (current["id"],),
                )
                conn.execute(
                    """INSERT INTO football_brief.shared_storage_events
                       (artifact_version_id,event,actor,details)
                       VALUES (%s,'artifact_superseded',%s,%s::jsonb)""",
                    (
                        current["id"],
                        actor,
                        _json({"replacement_version": version}),
                    ),
                )
            elif parent_id is not None:
                raise SharedArtifactError("artifact_parent_without_current")

            artifact = conn.execute(
                """INSERT INTO football_brief.shared_artifact_versions
                   (brand_id,portfolio_content_id,content_version,artifact_key,artifact_kind,
                    version,parent_version_id,status,original_asset_id,review_proxy_asset_id,
                    thumbnail_asset_id,retention_until,metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'current',%s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.brand_id,
                    request.portfolio_content_id,
                    request.content_version,
                    request.artifact_key,
                    request.artifact_kind.value,
                    version,
                    parent_id,
                    request.original_asset_id,
                    request.review_proxy_asset_id,
                    request.thumbnail_asset_id,
                    request.retention_until,
                    _json(request.metadata),
                    actor,
                ),
            ).fetchone()
            for role, object_row in object_rows.items():
                conn.execute(
                    """INSERT INTO football_brief.shared_artifact_object_roles
                       (artifact_version_id,storage_object_id,role)
                       VALUES (%s,%s,%s)""",
                    (artifact["id"], object_row["id"], role.value),
                )
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,artifact_version_id,event,actor,details)
                   VALUES (%s,%s,'artifact_version_created',%s,%s::jsonb)""",
                (
                    request.backend_id,
                    artifact["id"],
                    actor,
                    _json({
                        "artifact_key": request.artifact_key,
                        "version": version,
                        "roles": [role.value for role in object_rows],
                    }),
                ),
            )
        return self.detail(artifact_version_id=artifact["id"])

    def ensure_shared_object(
        self,
        *,
        asset_id: UUID,
        backend_id: UUID,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_active_operator(conn, actor)
            asset = conn.execute("SELECT * FROM football_brief.assets WHERE id=%s", (asset_id,)).fetchone()
            backend = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends WHERE id=%s",
                (backend_id,),
            ).fetchone()
            existing = conn.execute(
                """SELECT * FROM football_brief.shared_storage_objects
                   WHERE asset_id=%s AND backend_id=%s AND status='available'
                   ORDER BY created_at DESC LIMIT 1""",
                (asset_id, backend_id),
            ).fetchone()
        if not asset:
            raise SharedArtifactError("canonical_asset_not_found")
        if asset["size_bytes"] is None:
            raise SharedArtifactError("canonical_asset_size_required")
        if not backend:
            raise SharedArtifactError("shared_backend_not_found")
        if backend["status"] != "active":
            raise SharedArtifactError("shared_backend_not_active")
        provider = self.providers.provider(dict(backend))
        if existing:
            try:
                provider.verify(
                    object_key=existing["object_key"],
                    expected_sha256=asset["sha256"],
                    expected_size_bytes=int(asset["size_bytes"]),
                )
            except (SharedObjectMissing, SharedObjectHashMismatch) as exc:
                with self.database.transaction() as conn:
                    conn.execute(
                        """UPDATE football_brief.shared_storage_objects
                           SET status='missing' WHERE id=%s AND status='available'""",
                        (existing["id"],),
                    )
                raise SharedArtifactError("shared_object_verification_failed") from exc
            return dict(existing)

        source_path = self.source_resolver.resolve(asset["storage_uri"])
        object_key = content_addressed_key(
            sha256=asset["sha256"],
            filename=asset["original_filename"],
        )
        stored = provider.put_file(
            source_path,
            object_key=object_key,
            expected_sha256=asset["sha256"],
            expected_size_bytes=int(asset["size_bytes"]),
            mime_type=asset["mime_type"],
            metadata={
                "canonical_asset_id": str(asset_id),
                "asset_type": asset["asset_type"],
                "source_type": asset["source_type"],
            },
        )
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            duplicate = conn.execute(
                """SELECT * FROM football_brief.shared_storage_objects
                   WHERE asset_id=%s AND backend_id=%s AND object_key=%s""",
                (asset_id, backend_id, stored.object_key),
            ).fetchone()
            if duplicate:
                return dict(duplicate)
            row = conn.execute(
                """INSERT INTO football_brief.shared_storage_objects
                   (asset_id,backend_id,object_key,storage_uri,object_version,etag,sha256,
                    size_bytes,mime_type,status,verified_at,metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'available',now(),%s::jsonb,%s)
                   RETURNING *""",
                (
                    asset_id,
                    backend_id,
                    stored.object_key,
                    stored.storage_uri,
                    stored.object_version,
                    stored.etag,
                    stored.sha256,
                    stored.size_bytes,
                    stored.mime_type or asset["mime_type"],
                    _json(stored.metadata),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,storage_object_id,event,actor,details)
                   VALUES (%s,%s,'object_registered',%s,%s::jsonb),
                          (%s,%s,'object_verified',%s,%s::jsonb)""",
                (
                    backend_id,
                    row["id"],
                    actor,
                    _json({"asset_id": str(asset_id), "sha256": stored.sha256}),
                    backend_id,
                    row["id"],
                    actor,
                    _json({"size_bytes": stored.size_bytes}),
                ),
            )
        return dict(row)

    def detail(self, *, artifact_version_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            artifact = conn.execute(
                """SELECT sav.*,b.display_name AS brand_name,pc.title AS content_title
                   FROM football_brief.shared_artifact_versions sav
                   JOIN football_brief.brands b ON b.id=sav.brand_id
                   LEFT JOIN football_brief.portfolio_content pc ON pc.id=sav.portfolio_content_id
                   WHERE sav.id=%s""",
                (artifact_version_id,),
            ).fetchone()
            if not artifact:
                raise SharedArtifactError("shared_artifact_not_found")
            objects = conn.execute(
                """SELECT saor.role,sso.*,ssb.backend_key,ssb.driver,ssb.environment
                   FROM football_brief.shared_artifact_object_roles saor
                   JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE saor.artifact_version_id=%s ORDER BY saor.role""",
                (artifact_version_id,),
            ).fetchall()
            grants = conn.execute(
                """SELECT id,artifact_version_id,storage_object_id,brand_id,issued_to_operator_id,
                          access_purpose,expires_at,revoked_at,created_by,created_at
                   FROM football_brief.shared_access_grants
                   WHERE artifact_version_id=%s ORDER BY created_at DESC""",
                (artifact_version_id,),
            ).fetchall()
            events = conn.execute(
                """SELECT * FROM football_brief.shared_storage_events
                   WHERE artifact_version_id=%s ORDER BY created_at,id""",
                (artifact_version_id,),
            ).fetchall()
        return {
            "ok": True,
            "artifact": dict(artifact),
            "objects": [dict(row) for row in objects],
            "access_grants": [dict(row) for row in grants],
            "events": [dict(row) for row in events],
        }

    def list_artifacts(
        self,
        *,
        brand_ids: list[UUID] | None = None,
        content_id: UUID | None = None,
        include_history: bool = True,
    ) -> list[dict[str, Any]]:
        conditions = ["true"]
        values: list[Any] = []
        if brand_ids is not None:
            if not brand_ids:
                return []
            conditions.append("sav.brand_id=ANY(%s::uuid[])")
            values.append(brand_ids)
        if content_id:
            conditions.append("sav.portfolio_content_id=%s")
            values.append(content_id)
        if not include_history:
            conditions.append("sav.status='current'")
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT sav.*,b.display_name AS brand_name,pc.title AS content_title
                    FROM football_brief.shared_artifact_versions sav
                    JOIN football_brief.brands b ON b.id=sav.brand_id
                    LEFT JOIN football_brief.portfolio_content pc ON pc.id=sav.portfolio_content_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY sav.created_at DESC,sav.version DESC""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def issue_access(
        self,
        *,
        artifact_version_id: UUID,
        request: SignedAccessRequest,
        actor: str,
    ) -> SignedAccessResult:
        token = secrets.token_urlsafe(32)
        digest = token_digest(token)
        expires_at = _utcnow() + timedelta(seconds=request.expires_in_seconds)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """SELECT sav.brand_id,sav.status,saor.storage_object_id
                   FROM football_brief.shared_artifact_versions sav
                   JOIN football_brief.shared_artifact_object_roles saor
                     ON saor.artifact_version_id=sav.id AND saor.role=%s
                   JOIN football_brief.shared_storage_objects sso
                     ON sso.id=saor.storage_object_id AND sso.status='available'
                   WHERE sav.id=%s""",
                (request.role.value, artifact_version_id),
            ).fetchone()
            if not row:
                raise SharedArtifactError("shared_artifact_role_not_available")
            if row["status"] == "deleted":
                raise SharedArtifactError("shared_artifact_deleted")
            grant = conn.execute(
                """INSERT INTO football_brief.shared_access_grants
                   (artifact_version_id,storage_object_id,brand_id,issued_to_operator_id,
                    access_purpose,token_digest,expires_at,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    artifact_version_id,
                    row["storage_object_id"],
                    row["brand_id"],
                    request.issued_to_operator_id,
                    request.access_purpose,
                    digest,
                    expires_at,
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_access_events
                   (grant_id,event,details) VALUES (%s,'issued',%s::jsonb)""",
                (
                    grant["id"],
                    _json({"role": request.role.value, "expires_in_seconds": request.expires_in_seconds}),
                ),
            )
        path = f"/shared-media/{grant['id']}?token={quote(token, safe='')}"
        return SignedAccessResult(
            grant_id=grant["id"],
            url=f"{self.public_base_url}{path}" if self.public_base_url else path,
            expires_at=expires_at,
            artifact_version_id=artifact_version_id,
            storage_object_id=row["storage_object_id"],
            role=request.role,
        )

    def consume_access(
        self,
        *,
        grant_id: UUID,
        token: str,
        remote_address: str | None = None,
        user_agent: str | None = None,
    ) -> SharedAccessTarget:
        digest = token_digest(token)
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT sag.*,sav.status AS artifact_status,sso.object_key,sso.status AS object_status,
                          sso.mime_type,a.original_filename,ssb.*
                   FROM football_brief.shared_access_grants sag
                   JOIN football_brief.shared_artifact_versions sav ON sav.id=sag.artifact_version_id
                   JOIN football_brief.shared_storage_objects sso ON sso.id=sag.storage_object_id
                   JOIN football_brief.assets a ON a.id=sso.asset_id
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE sag.id=%s FOR UPDATE OF sag""",
                (grant_id,),
            ).fetchone()
            if not row:
                raise SharedArtifactError("access_grant_not_found")
            event = "accessed"
            error_code = None
            if not hmac.compare_digest(str(row["token_digest"]), digest):
                event, error_code = "denied", "access_token_invalid"
            elif row["revoked_at"] is not None:
                event, error_code = "denied", "access_grant_revoked"
            elif row["expires_at"] <= _utcnow():
                event, error_code = "expired", "access_grant_expired"
            elif row["artifact_status"] == "deleted" or row["object_status"] != "available":
                event, error_code = "denied", "shared_object_unavailable"
            elif row["status"] != "active":
                event, error_code = "denied", "shared_backend_unavailable"
            conn.execute(
                """INSERT INTO football_brief.shared_access_events
                   (grant_id,event,remote_address_hash,user_agent_hash,details)
                   VALUES (%s,%s,%s,%s,%s::jsonb)""",
                (
                    grant_id,
                    event,
                    self._optional_digest(remote_address),
                    self._optional_digest(user_agent),
                    _json({"error_code": error_code} if error_code else {"backend_key": row["backend_key"]}),
                ),
            )
            if error_code:
                raise SharedArtifactError(error_code)
            remaining = max(1, int((row["expires_at"] - _utcnow()).total_seconds()))
            backend = dict(row)
        provider = self.providers.provider(backend)
        return provider.access_target(
            object_key=row["object_key"],
            expires_in_seconds=min(remaining, 3600),
            mime_type=row["mime_type"],
            filename=row["original_filename"],
        )

    def revoke_access(self, *, grant_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """UPDATE football_brief.shared_access_grants
                   SET revoked_at=now(),revoked_by=%s
                   WHERE id=%s AND revoked_at IS NULL RETURNING *""",
                (actor, grant_id),
            ).fetchone()
            if not row:
                raise SharedArtifactError("access_grant_not_found_or_revoked")
            conn.execute(
                """INSERT INTO football_brief.shared_access_events
                   (grant_id,event,details) VALUES (%s,'revoked',%s::jsonb)""",
                (grant_id, _json({"revoked_by": actor})),
            )
        return {"ok": True, "grant": self._public_grant(row)}

    def set_legal_hold(
        self,
        *,
        artifact_version_id: UUID,
        request: LegalHoldRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            artifact = conn.execute(
                "SELECT * FROM football_brief.shared_artifact_versions WHERE id=%s FOR UPDATE",
                (artifact_version_id,),
            ).fetchone()
            if not artifact:
                raise SharedArtifactError("shared_artifact_not_found")
            if request.enabled:
                updated = conn.execute(
                    """UPDATE football_brief.shared_artifact_versions
                       SET legal_hold=true,legal_hold_reason=%s,legal_hold_set_by=%s,legal_hold_set_at=now()
                       WHERE id=%s RETURNING *""",
                    (request.reason, actor, artifact_version_id),
                ).fetchone()
                event = "legal_hold_set"
            else:
                updated = conn.execute(
                    """UPDATE football_brief.shared_artifact_versions
                       SET legal_hold=false,legal_hold_reason=NULL,legal_hold_set_by=NULL,legal_hold_set_at=NULL
                       WHERE id=%s RETURNING *""",
                    (artifact_version_id,),
                ).fetchone()
                event = "legal_hold_released"
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (artifact_version_id,event,actor,details)
                   VALUES (%s,%s,%s,%s::jsonb)""",
                (artifact_version_id, event, actor, _json({"reason": request.reason})),
            )
        return self.detail(artifact_version_id=updated["id"])

    def delete_artifact(
        self,
        *,
        artifact_version_id: UUID,
        request: DeletionRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            artifact = conn.execute(
                "SELECT * FROM football_brief.shared_artifact_versions WHERE id=%s FOR UPDATE",
                (artifact_version_id,),
            ).fetchone()
            if not artifact:
                raise SharedArtifactError("shared_artifact_not_found")
            conn.execute(
                """UPDATE football_brief.shared_artifact_versions
                   SET status='deletion_pending' WHERE id=%s""",
                (artifact_version_id,),
            )
            objects = conn.execute(
                """SELECT sso.*,ssb.backend_key,ssb.driver,ssb.environment,ssb.endpoint_url,
                          ssb.bucket_name,ssb.base_prefix,ssb.region,ssb.credential_secret_ref,
                          ssb.public_base_url,ssb.configuration,ssb.status AS backend_status
                   FROM football_brief.shared_artifact_object_roles saor
                   JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE saor.artifact_version_id=%s""",
                (artifact_version_id,),
            ).fetchall()
            deletable: list[dict[str, Any]] = []
            for object_row in objects:
                other = conn.execute(
                    """SELECT count(*) AS count
                       FROM football_brief.shared_artifact_object_roles other_role
                       JOIN football_brief.shared_artifact_versions other_artifact
                         ON other_artifact.id=other_role.artifact_version_id
                       WHERE other_role.storage_object_id=%s
                         AND other_role.artifact_version_id<>%s
                         AND other_artifact.status NOT IN ('deletion_pending','deleted')""",
                    (object_row["id"], artifact_version_id),
                ).fetchone()
                if other["count"] == 0 and object_row["status"] != "deleted":
                    conn.execute(
                        """UPDATE football_brief.shared_storage_objects
                           SET status='deletion_pending' WHERE id=%s""",
                        (object_row["id"],),
                    )
                    deletable.append(dict(object_row))
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (artifact_version_id,event,actor,details)
                   VALUES (%s,'deletion_requested',%s,%s::jsonb)""",
                (
                    artifact_version_id,
                    actor,
                    _json({"rationale": request.rationale, "object_count": len(deletable)}),
                ),
            )

        for object_row in deletable:
            provider = self.providers.provider(object_row)
            provider.delete(object_key=object_row["object_key"])
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.shared_storage_objects
                       SET status='deleted',deleted_at=now() WHERE id=%s""",
                    (object_row["id"],),
                )
                conn.execute(
                    """INSERT INTO football_brief.shared_storage_events
                       (backend_id,storage_object_id,artifact_version_id,event,actor,details)
                       VALUES (%s,%s,%s,'object_deleted',%s,'{}'::jsonb)""",
                    (object_row["backend_id"], object_row["id"], artifact_version_id, actor),
                )
        with self.database.transaction() as conn:
            deleted = conn.execute(
                """UPDATE football_brief.shared_artifact_versions
                   SET status='deleted',deleted_at=now() WHERE id=%s RETURNING *""",
                (artifact_version_id,),
            ).fetchone()
        return {"ok": True, "artifact": dict(deleted), "deleted_object_count": len(deletable)}

    def prepare_backup(
        self,
        *,
        request: BackupPrepareRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            backend = conn.execute(
                "SELECT * FROM football_brief.shared_storage_backends WHERE id=%s",
                (request.backend_id,),
            ).fetchone()
            if not backend:
                raise SharedArtifactError("shared_backend_not_found")
            rows = conn.execute(
                """SELECT sso.id,sso.asset_id,sso.object_key,sso.storage_uri,sso.object_version,
                          sso.sha256,sso.size_bytes,sso.mime_type,sso.status,
                          a.asset_type,a.source_type,a.lifecycle_status,
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
                   JOIN football_brief.assets a ON a.id=sso.asset_id
                   LEFT JOIN football_brief.shared_artifact_object_roles saor ON saor.storage_object_id=sso.id
                   LEFT JOIN football_brief.shared_artifact_versions sav ON sav.id=saor.artifact_version_id
                   WHERE sso.backend_id=%s AND sso.status='available'
                   GROUP BY sso.id,a.id
                   ORDER BY sso.object_key""",
                (request.backend_id,),
            ).fetchall()
            objects = [dict(row) for row in rows]
            manifest = {
                "schema": "shared-artifact-backup-v1",
                "backend": {
                    "id": str(backend["id"]),
                    "backend_key": backend["backend_key"],
                    "driver": backend["driver"],
                    "environment": backend["environment"],
                },
                "metadata": request.metadata,
                "objects": objects,
            }
            artifact_ids = {
                str(role["artifact_version_id"])
                for item in objects
                for role in item["artifact_roles"]
            }
            total_size = sum(int(item["size_bytes"]) for item in objects)
            digest = _sha256_json(manifest)
            snapshot = conn.execute(
                """INSERT INTO football_brief.shared_backup_snapshots
                   (backend_id,status,artifact_count,object_count,total_size_bytes,
                    manifest,manifest_sha256,created_by)
                   VALUES (%s,'prepared',%s,%s,%s,%s::jsonb,%s,%s) RETURNING *""",
                (
                    request.backend_id,
                    len(artifact_ids),
                    len(objects),
                    total_size,
                    _json(manifest),
                    digest,
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,event,actor,details)
                   VALUES (%s,'backup_prepared',%s,%s::jsonb)""",
                (
                    request.backend_id,
                    actor,
                    _json({"snapshot_id": str(snapshot["id"]), "object_count": len(objects)}),
                ),
            )
        return {"ok": True, "snapshot": dict(snapshot)}

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
        results = []
        all_verified = True
        manifest = dict(snapshot["manifest"])
        for item in manifest.get("objects", []):
            metadata_matches = False
            checksum_matches = False
            observed_sha = None
            restored_uri = f"unavailable://{item['object_key']}"
            details: dict[str, Any] = {}
            with self.database.connection() as conn:
                current = conn.execute(
                    """SELECT id,asset_id,object_key,sha256,size_bytes,mime_type
                       FROM football_brief.shared_storage_objects WHERE id=%s""",
                    (item["id"],),
                ).fetchone()
            metadata_matches = bool(
                current
                and str(current["asset_id"]) == str(item["asset_id"])
                and current["object_key"] == item["object_key"]
                and current["sha256"] == item["sha256"]
                and int(current["size_bytes"]) == int(item["size_bytes"])
            )
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
            snapshot = conn.execute(
                f"""UPDATE football_brief.shared_backup_snapshots
                    SET status=%s,{ 'verified_at=now()' if all_verified else 'failed_at=now()' }
                    WHERE id=%s AND status='prepared' RETURNING *""",
                (final_status, snapshot_id),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.shared_storage_events
                   (backend_id,event,actor,details)
                   VALUES (%s,%s,%s,%s::jsonb)""",
                (
                    snapshot["backend_id"],
                    "restore_verified" if all_verified else "restore_failed",
                    actor,
                    _json({"snapshot_id": str(snapshot_id), "verification_count": len(results)}),
                ),
            )
        return {"ok": all_verified, "snapshot": dict(snapshot), "verifications": results}

    @staticmethod
    def _optional_digest(value: str | None) -> str | None:
        if not value:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_grant(row: Any) -> dict[str, Any]:
        return {
            key: row[key]
            for key in (
                "id",
                "artifact_version_id",
                "storage_object_id",
                "brand_id",
                "issued_to_operator_id",
                "access_purpose",
                "expires_at",
                "revoked_at",
                "revoked_by",
                "created_by",
                "created_at",
            )
        }

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not row:
            raise SharedArtifactError("operator_inactive_or_missing")
