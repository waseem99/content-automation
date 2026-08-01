from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.application.assets.hashing import inspect_file
from src.application.campaign_storage.download_patch import install_google_drive_download_patch
from src.application.campaign_storage.google_drive import GoogleDriveError, GoogleDriveStorage
from src.application.campaign_storage.service import CampaignStorageError, CampaignStorageService

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


install_google_drive_download_patch()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class CampaignStorageRecoveryService:
    def __init__(self, database: "Database", drive: GoogleDriveStorage | Any | None = None) -> None:
        self.database = database
        self.drive = drive or GoogleDriveStorage()
        self.storage = CampaignStorageService(database, drive=self.drive)

    def recover_missing_local(
        self,
        *,
        asset_id: UUID,
        actor: str,
        destination: Path | None = None,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            if operator is None:
                raise CampaignStorageError("operator_inactive_or_missing")
            asset = conn.execute(
                "SELECT * FROM football_brief.assets WHERE id=%s",
                (asset_id,),
            ).fetchone()
            if asset is None:
                raise CampaignStorageError("asset_not_found")
            local = conn.execute(
                """SELECT * FROM football_brief.asset_storage_locations
                   WHERE asset_id=%s AND provider='local' AND status IN ('missing','checksum_mismatch')
                   ORDER BY created_at,id LIMIT 1""",
                (asset_id,),
            ).fetchone()
            drive_location = conn.execute(
                """SELECT * FROM football_brief.asset_storage_locations
                   WHERE asset_id=%s AND provider='google_drive' AND status='available'
                   ORDER BY verified_at DESC NULLS LAST,created_at,id LIMIT 1""",
                (asset_id,),
            ).fetchone()
        if local is None:
            raise CampaignStorageError("missing_local_location_required")
        if drive_location is None:
            raise CampaignStorageError("available_drive_location_required")

        file_id = self.storage._drive_file_id(str(drive_location["locator"]))
        expected_sha = str(asset["sha256"])
        expected_size = int(asset["size_bytes"] or drive_location["size_bytes"] or 0)
        metadata = self.drive.metadata(file_id, expected_sha256=expected_sha)
        if metadata.sha256 != expected_sha or metadata.size_bytes != expected_size:
            raise CampaignStorageError(
                "google_drive_checksum_mismatch",
                details={
                    "expected_sha256": expected_sha,
                    "observed_sha256": metadata.sha256,
                    "expected_size_bytes": expected_size,
                    "observed_size_bytes": metadata.size_bytes,
                },
            )

        if destination is None:
            root = self.storage.allowed_local_roots[0]
            filename = str(asset.get("original_filename") or f"{asset_id}.bin")
            destination = root / "recovered" / str(asset_id) / filename
        destination = self.storage._allowed_local_path(destination, require_exists=False)
        temporary_destination = destination.with_name(f".{destination.name}.download")
        temporary_destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            downloaded = self.drive.download_file(file_id, temporary_destination)
            inspection = inspect_file(downloaded)
            if inspection.sha256 != expected_sha or inspection.size_bytes != expected_size:
                raise CampaignStorageError(
                    "recovered_file_checksum_mismatch",
                    details={
                        "expected_sha256": expected_sha,
                        "observed_sha256": inspection.sha256,
                        "expected_size_bytes": expected_size,
                        "observed_size_bytes": inspection.size_bytes,
                    },
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(downloaded, destination)
            with self.database.transaction() as conn:
                row = conn.execute(
                    """UPDATE football_brief.asset_storage_locations
                       SET locator=%s,status='available',sha256=%s,size_bytes=%s,
                           verified_at=now(),last_checked_at=now(),last_error_code=NULL,
                           reconciliation_metadata=%s::jsonb
                       WHERE id=%s RETURNING *""",
                    (
                        destination.as_uri(),
                        inspection.sha256,
                        inspection.size_bytes,
                        _json({
                            "verification": "drive_recovery_full_sha256",
                            "source_drive_location_id": str(drive_location["id"]),
                            "file_id": file_id,
                        }),
                        local["id"],
                    ),
                ).fetchone()
                event = conn.execute(
                    """INSERT INTO football_brief.asset_storage_recovery_events
                       (asset_id,source_location_id,destination_location_id,status,
                        expected_sha256,observed_sha256,size_bytes,details,requested_by,completed_at)
                       VALUES (%s,%s,%s,'succeeded',%s,%s,%s,%s::jsonb,%s,now())
                       RETURNING *""",
                    (
                        asset_id,
                        drive_location["id"],
                        local["id"],
                        expected_sha,
                        inspection.sha256,
                        inspection.size_bytes,
                        _json({"destination": destination.as_uri(), "file_id": file_id}),
                        actor,
                    ),
                ).fetchone()
            return {"ok": True, "location": dict(row), "event": dict(event)}
        except (CampaignStorageError, GoogleDriveError, FileNotFoundError, OSError) as exc:
            temporary_destination.unlink(missing_ok=True)
            with self.database.transaction() as conn:
                conn.execute(
                    """INSERT INTO football_brief.asset_storage_recovery_events
                       (asset_id,source_location_id,destination_location_id,status,
                        expected_sha256,error_code,details,requested_by,completed_at)
                       VALUES (%s,%s,%s,'failed',%s,%s,%s::jsonb,%s,now())""",
                    (
                        asset_id,
                        drive_location["id"],
                        local["id"],
                        expected_sha,
                        getattr(exc, "code", type(exc).__name__),
                        _json({"message": str(exc)}),
                        actor,
                    ),
                )
            raise


__all__ = ["CampaignStorageRecoveryService"]
