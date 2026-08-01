from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import unquote, urlparse
from uuid import UUID

from src.application.assets.hashing import inspect_file
from src.application.campaign_storage.google_drive import (
    GoogleDriveError,
    GoogleDriveNotConfigured,
    GoogleDriveStorage,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class CampaignStorageError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class CampaignStorageService:
    def __init__(self, database: "Database", drive: GoogleDriveStorage | None = None) -> None:
        self.database = database
        self.drive = drive or GoogleDriveStorage()
        roots = {
            Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).expanduser().resolve(),
            Path(os.getenv("PORTFOLIO_MEDIA_ROOT", ".runtime/artifacts")).expanduser().resolve(),
            Path(os.getenv("LOCAL_RUNTIME_ROOT", ".runtime")).expanduser().resolve(),
        }
        self.allowed_local_roots = tuple(sorted(roots, key=lambda value: str(value)))

    def locations(self, *, asset_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            asset = self._asset(conn, asset_id)
            rows = conn.execute(
                """SELECT * FROM football_brief.asset_storage_locations
                   WHERE asset_id=%s ORDER BY provider,created_at,id""",
                (asset_id,),
            ).fetchall()
        return {
            "ok": True,
            "kind": "asset_storage_locations",
            "asset": dict(asset),
            "locations": [dict(row) for row in rows],
            "providers": ["local", "google_drive"],
            "google_drive_configured": self.drive.configured,
        }

    def register_local(
        self,
        *,
        asset_id: UUID,
        path: Path,
        actor: str,
    ) -> dict[str, Any]:
        path = self._allowed_local_path(path, require_exists=True)
        inspection = inspect_file(path)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            asset = self._asset(conn, asset_id, for_update=True)
            self._require_asset_match(asset, inspection.sha256, inspection.size_bytes)
            row = conn.execute(
                """INSERT INTO football_brief.asset_storage_locations
                   (asset_id,provider,locator,status,sha256,size_bytes,verified_at,created_by,metadata,
                    last_checked_at,last_error_code,reconciliation_metadata)
                   VALUES (%s,'local',%s,'available',%s,%s,now(),%s,%s::jsonb,now(),NULL,%s::jsonb)
                   ON CONFLICT (asset_id,provider,locator) DO UPDATE SET
                     status='available',sha256=EXCLUDED.sha256,size_bytes=EXCLUDED.size_bytes,
                     verified_at=now(),last_checked_at=now(),last_error_code=NULL,
                     reconciliation_metadata=EXCLUDED.reconciliation_metadata
                   RETURNING *""",
                (
                    asset_id,
                    path.as_uri(),
                    inspection.sha256,
                    inspection.size_bytes,
                    actor,
                    _json({"filename": path.name, "mime_type": inspection.mime_type}),
                    _json({"verification": "full_local_sha256"}),
                ),
            ).fetchone()
        return {"ok": True, "kind": "local_asset_location", "location": dict(row)}

    def upload_google_drive(
        self,
        *,
        asset_id: UUID,
        actor: str,
        source_path: Path | None = None,
        parent_folder_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            self.drive.require_configured()
        except GoogleDriveNotConfigured as exc:
            raise CampaignStorageError("google_drive_not_configured") from exc
        with self.database.connection() as conn:
            asset = self._asset(conn, asset_id)
            if source_path is None:
                local = conn.execute(
                    """SELECT locator FROM football_brief.asset_storage_locations
                       WHERE asset_id=%s AND provider='local' AND status='available'
                       ORDER BY verified_at DESC NULLS LAST,created_at DESC LIMIT 1""",
                    (asset_id,),
                ).fetchone()
                if local is None:
                    source_path = self._path_from_asset_uri(str(asset["storage_uri"]))
                else:
                    source_path = self._path_from_local_locator(str(local["locator"]))
        if source_path is None:
            raise CampaignStorageError("local_source_location_required_for_drive_upload")
        source_path = self._allowed_local_path(source_path, require_exists=True)
        inspection = inspect_file(source_path)
        self._require_asset_match(asset, inspection.sha256, inspection.size_bytes)
        try:
            uploaded = self.drive.upload_file(
                source_path,
                asset_id=str(asset_id),
                sha256=inspection.sha256,
                mime_type=inspection.mime_type,
                parent_folder_id=parent_folder_id,
                filename=asset.get("original_filename") or source_path.name,
            )
        except GoogleDriveError as exc:
            raise CampaignStorageError("google_drive_upload_failed", details={"message": str(exc)}) from exc
        locator = f"gdrive://{uploaded.file_id}"
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            self._asset(conn, asset_id, for_update=True)
            row = conn.execute(
                """INSERT INTO football_brief.asset_storage_locations
                   (asset_id,provider,locator,status,sha256,size_bytes,verified_at,created_by,metadata,
                    last_checked_at,last_error_code,reconciliation_metadata)
                   VALUES (%s,'google_drive',%s,'available',%s,%s,now(),%s,%s::jsonb,now(),NULL,%s::jsonb)
                   ON CONFLICT (asset_id,provider,locator) DO UPDATE SET
                     status='available',sha256=EXCLUDED.sha256,size_bytes=EXCLUDED.size_bytes,
                     verified_at=now(),last_checked_at=now(),last_error_code=NULL,
                     metadata=EXCLUDED.metadata,reconciliation_metadata=EXCLUDED.reconciliation_metadata
                   RETURNING *""",
                (
                    asset_id,
                    locator,
                    uploaded.sha256,
                    uploaded.size_bytes,
                    actor,
                    _json(
                        {
                            "file_id": uploaded.file_id,
                            "name": uploaded.name,
                            "mime_type": uploaded.mime_type,
                            "parent_folder_id": uploaded.parent_folder_id,
                            **uploaded.metadata,
                        }
                    ),
                    _json({"verification": "drive_size_and_sha256_app_property"}),
                ),
            ).fetchone()
        return {"ok": True, "kind": "google_drive_asset_location", "location": dict(row)}

    def reconcile(
        self,
        *,
        actor: str,
        provider: Literal["local", "google_drive"] | None = None,
        strict_drive_download: bool = False,
        limit: int = 1000,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 10000:
            raise CampaignStorageError("reconciliation_limit_must_be_1_to_10000")
        if provider == "google_drive" and not self.drive.configured:
            raise CampaignStorageError("google_drive_not_configured")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            run = conn.execute(
                """INSERT INTO football_brief.asset_storage_reconciliation_runs
                   (provider,status,requested_by,details)
                   VALUES (%s,'running',%s,%s::jsonb) RETURNING *""",
                (
                    provider,
                    actor,
                    _json({"strict_drive_download": strict_drive_download, "limit": limit}),
                ),
            ).fetchone()
            conditions = ["location.status<>'archived'"]
            values: list[Any] = []
            if provider:
                conditions.append("location.provider=%s")
                values.append(provider)
            values.append(limit)
            rows = conn.execute(
                f"""SELECT location.*,asset.storage_uri AS asset_storage_uri,
                            asset.sha256 AS asset_sha256,asset.size_bytes AS asset_size_bytes
                     FROM football_brief.asset_storage_locations location
                     JOIN football_brief.assets asset ON asset.id=location.asset_id
                     WHERE {' AND '.join(conditions)}
                     ORDER BY location.last_checked_at NULLS FIRST,location.created_at
                     LIMIT %s
                     FOR UPDATE OF location SKIP LOCKED""",
                tuple(values),
            ).fetchall()
        counters = {"checked": 0, "available": 0, "missing": 0, "mismatch": 0, "failed": 0}
        results: list[dict[str, Any]] = []
        for raw in rows:
            location = dict(raw)
            result = self._reconcile_location(location, strict_drive_download=strict_drive_download)
            counters["checked"] += 1
            if result["status"] == "available":
                counters["available"] += 1
            elif result["status"] == "missing":
                counters["missing"] += 1
            elif result["status"] == "checksum_mismatch":
                counters["mismatch"] += 1
            else:
                counters["failed"] += 1
            results.append(result)
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.asset_storage_locations
                       SET status=%s,verified_at=CASE WHEN %s='available' THEN now() ELSE verified_at END,
                           last_checked_at=now(),last_error_code=%s,
                           reconciliation_metadata=%s::jsonb
                       WHERE id=%s""",
                    (
                        result["status"],
                        result["status"],
                        result.get("error_code"),
                        _json(result.get("metadata") or {}),
                        location["id"],
                    ),
                )
        final_status = "completed" if counters["failed"] == 0 else "partial"
        with self.database.transaction() as conn:
            completed = conn.execute(
                """UPDATE football_brief.asset_storage_reconciliation_runs
                   SET status=%s,checked_count=%s,available_count=%s,missing_count=%s,
                       mismatch_count=%s,details=details || %s::jsonb,completed_at=now()
                   WHERE id=%s RETURNING *""",
                (
                    final_status,
                    counters["checked"],
                    counters["available"],
                    counters["missing"],
                    counters["mismatch"],
                    _json({"failed_count": counters["failed"], "sample": results[:50]}),
                    run["id"],
                ),
            ).fetchone()
        return {
            "ok": final_status == "completed",
            "kind": "asset_storage_reconciliation",
            "run": dict(completed),
            "counts": counters,
            "results": results,
        }

    def _reconcile_location(
        self,
        location: dict[str, Any],
        *,
        strict_drive_download: bool,
    ) -> dict[str, Any]:
        provider = str(location["provider"])
        expected_sha = str(location["asset_sha256"])
        expected_size = int(location["asset_size_bytes"] or location["size_bytes"] or 0)
        if provider == "local":
            try:
                path = self._path_from_local_locator(str(location["locator"]))
                path = self._allowed_local_path(path, require_exists=True)
                inspected = inspect_file(path)
            except (FileNotFoundError, OSError, ValueError, CampaignStorageError):
                return {
                    "location_id": str(location["id"]),
                    "provider": provider,
                    "status": "missing",
                    "error_code": "local_file_missing",
                }
            if inspected.sha256 != expected_sha or inspected.size_bytes != expected_size:
                return {
                    "location_id": str(location["id"]),
                    "provider": provider,
                    "status": "checksum_mismatch",
                    "error_code": "local_checksum_mismatch",
                    "metadata": {
                        "observed_sha256": inspected.sha256,
                        "observed_size_bytes": inspected.size_bytes,
                    },
                }
            return {
                "location_id": str(location["id"]),
                "provider": provider,
                "status": "available",
                "metadata": {"verification": "full_local_sha256"},
            }
        if provider != "google_drive":
            return {
                "location_id": str(location["id"]),
                "provider": provider,
                "status": "missing",
                "error_code": "unsupported_storage_provider",
            }
        file_id = self._drive_file_id(str(location["locator"]))
        try:
            metadata = self.drive.metadata(file_id, expected_sha256=expected_sha)
            observed_sha = metadata.sha256
            observed_size = metadata.size_bytes
            verification = "drive_size_and_sha256_app_property"
            if strict_drive_download:
                observed_sha, observed_size = self.drive.download_sha256(file_id)
                verification = "full_drive_download_sha256"
        except FileNotFoundError:
            return {
                "location_id": str(location["id"]),
                "provider": provider,
                "status": "missing",
                "error_code": "google_drive_file_missing",
            }
        except GoogleDriveError as exc:
            return {
                "location_id": str(location["id"]),
                "provider": provider,
                "status": "missing",
                "error_code": "google_drive_reconciliation_failed",
                "metadata": {"message": str(exc)},
            }
        if observed_sha != expected_sha or observed_size != expected_size:
            return {
                "location_id": str(location["id"]),
                "provider": provider,
                "status": "checksum_mismatch",
                "error_code": "google_drive_checksum_mismatch",
                "metadata": {
                    "verification": verification,
                    "observed_sha256": observed_sha,
                    "observed_size_bytes": observed_size,
                },
            }
        return {
            "location_id": str(location["id"]),
            "provider": provider,
            "status": "available",
            "metadata": {"verification": verification, "file_id": file_id},
        }

    def _allowed_local_path(self, path: Path, *, require_exists: bool) -> Path:
        resolved = path.expanduser().resolve(strict=require_exists)
        if not any(self._is_relative_to(resolved, root) for root in self.allowed_local_roots):
            raise CampaignStorageError(
                "local_path_outside_allowed_roots",
                details={"path": str(resolved), "allowed_roots": [str(root) for root in self.allowed_local_roots]},
            )
        if require_exists and not resolved.is_file():
            raise FileNotFoundError(resolved)
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _path_from_local_locator(locator: str) -> Path:
        parsed = urlparse(locator)
        if parsed.scheme != "file":
            raise CampaignStorageError("invalid_local_storage_locator")
        path = unquote(parsed.path)
        if os.name == "nt" and path.startswith("/") and len(path) >= 3 and path[2] == ":":
            path = path[1:]
        return Path(path)

    @staticmethod
    def _path_from_asset_uri(uri: str) -> Path | None:
        parsed = urlparse(uri)
        if parsed.scheme == "file":
            return CampaignStorageService._path_from_local_locator(uri)
        if parsed.scheme in {"workspace", "managed"}:
            candidate = unquote(parsed.path or "")
            return Path(candidate) if candidate else None
        return None

    @staticmethod
    def _drive_file_id(locator: str) -> str:
        parsed = urlparse(locator)
        if parsed.scheme != "gdrive" or not parsed.netloc:
            raise CampaignStorageError("invalid_google_drive_storage_locator")
        return parsed.netloc

    @staticmethod
    def _require_asset_match(asset: Any, sha256: str, size_bytes: int) -> None:
        if str(asset["sha256"]) != sha256 or int(asset["size_bytes"] or 0) != int(size_bytes):
            raise CampaignStorageError(
                "asset_bytes_do_not_match_canonical_registry",
                details={
                    "expected_sha256": str(asset["sha256"]),
                    "observed_sha256": sha256,
                    "expected_size_bytes": int(asset["size_bytes"] or 0),
                    "observed_size_bytes": int(size_bytes),
                },
            )

    @staticmethod
    def _asset(conn: Any, asset_id: UUID, *, for_update: bool = False) -> Any:
        suffix = " FOR UPDATE" if for_update else ""
        row = conn.execute(
            f"""SELECT id,asset_type,source_type,lifecycle_status,original_filename,
                       storage_uri,sha256,mime_type,size_bytes,metadata
                FROM football_brief.assets WHERE id=%s{suffix}""",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise CampaignStorageError("asset_not_found")
        return row

    @staticmethod
    def _require_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if row is None:
            raise CampaignStorageError("operator_inactive_or_missing")


__all__ = ["CampaignStorageError", "CampaignStorageService"]
