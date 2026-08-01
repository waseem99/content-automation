from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.campaign_storage.google_drive import GoogleDriveError, GoogleDriveFile
from src.application.campaign_storage.recovery import CampaignStorageRecoveryService
from src.application.campaign_storage.service import CampaignStorageService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _key() -> str:
    return datetime.now(timezone.utc).strftime("p129-%Y%m%dt%H%M%S%fz")


def _timed(timings: dict[str, float], key: str, function, *args, **kwargs):
    started = time.perf_counter()
    result = function(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


@dataclass
class FakeDrive:
    objects: dict[str, bytes]
    outage: bool = False
    metadata_calls: int = 0
    download_calls: int = 0

    @property
    def configured(self) -> bool:
        return True

    def require_configured(self) -> None:
        return None

    def metadata(self, file_id: str, *, expected_sha256: str | None = None) -> GoogleDriveFile:
        self.metadata_calls += 1
        if self.outage:
            raise GoogleDriveError("simulated Drive outage")
        if file_id not in self.objects:
            raise FileNotFoundError(file_id)
        payload = self.objects[file_id]
        digest = _sha_bytes(payload)
        if expected_sha256 and digest != expected_sha256:
            raise GoogleDriveError("simulated canonical SHA mismatch")
        return GoogleDriveFile(
            file_id=file_id,
            name=f"{file_id}.bin",
            size_bytes=len(payload),
            sha256=digest,
            mime_type="application/octet-stream",
            parent_folder_id="p129",
            metadata={"simulated": True},
        )

    def download_sha256(self, file_id: str) -> tuple[str, int]:
        if self.outage:
            raise GoogleDriveError("simulated Drive outage")
        payload = self.objects[file_id]
        return _sha_bytes(payload), len(payload)

    def download_file(self, file_id: str, destination: Path) -> Path:
        self.download_calls += 1
        if self.outage:
            raise GoogleDriveError("simulated Drive outage")
        payload = self.objects[file_id]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return destination


def _seed(
    database: Database,
    *,
    acceptance_key: str,
    assets: int,
    samples: list[bytes],
    local_paths: list[Path],
    actor: str,
) -> list[UUID]:
    if assets < len(samples):
        raise ValueError("assets must cover the real samples")
    with database.transaction() as conn:
        sample_ids: list[UUID] = []
        for ordinal, (payload, path) in enumerate(zip(samples, local_paths), start=1):
            digest = _sha_bytes(payload)
            asset = conn.execute(
                """INSERT INTO football_brief.assets
                   (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                    sha256,mime_type,size_bytes,metadata,created_by)
                   VALUES ('document','owned','approved',%s,%s,%s,'application/octet-stream',%s,%s::jsonb,%s)
                   RETURNING id""",
                (
                    f"sample-{ordinal}.bin",
                    path.as_uri(),
                    digest,
                    len(payload),
                    _json({
                        "p129_acceptance": acceptance_key,
                        "ordinal": ordinal,
                        "original_sha256": digest,
                        "real_sample": True,
                    }),
                    actor,
                ),
            ).fetchone()
            sample_ids.append(UUID(str(asset["id"])))
        if assets > len(samples):
            conn.execute(
                """INSERT INTO football_brief.assets
                   (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                    sha256,mime_type,size_bytes,metadata,created_by)
                   SELECT 'document','owned','approved',
                          'synthetic-' || lpad(value::text,8,'0') || '.bin',
                          'workspace://p129/' || %s || '/' || value::text,
                          encode(digest((%s || ':' || value::text)::bytea,'sha256'),'hex'),
                          'application/octet-stream',32,
                          jsonb_build_object(
                              'p129_acceptance',%s,
                              'ordinal',value,
                              'original_sha256',encode(digest((%s || ':' || value::text)::bytea,'sha256'),'hex'),
                              'real_sample',false
                          ),%s
                   FROM generate_series(%s,%s) value""",
                (
                    acceptance_key,
                    acceptance_key,
                    acceptance_key,
                    acceptance_key,
                    actor,
                    len(samples) + 1,
                    assets,
                ),
            )
        conn.execute(
            """INSERT INTO football_brief.asset_storage_locations
               (asset_id,provider,locator,status,sha256,size_bytes,verified_at,created_by,
                metadata,last_checked_at,reconciliation_metadata)
               SELECT asset.id,'local',
                      CASE WHEN (asset.metadata->>'real_sample')::boolean
                           THEN asset.storage_uri
                           ELSE 'file:///synthetic/p129/' || %s || '/' || asset.id::text END,
                      'available',asset.sha256,asset.size_bytes,now(),%s,
                      jsonb_build_object('p129_acceptance',%s,'synthetic',NOT (asset.metadata->>'real_sample')::boolean),
                      CASE WHEN (asset.metadata->>'real_sample')::boolean THEN NULL ELSE now() END,
                      jsonb_build_object('seeded',true)
               FROM football_brief.assets asset
               WHERE asset.metadata->>'p129_acceptance'=%s""",
            (acceptance_key, actor, acceptance_key, acceptance_key),
        )
        conn.execute(
            """INSERT INTO football_brief.asset_storage_locations
               (asset_id,provider,locator,status,sha256,size_bytes,verified_at,created_by,
                metadata,last_checked_at,reconciliation_metadata)
               SELECT asset.id,'google_drive',
                      CASE WHEN (asset.metadata->>'real_sample')::boolean
                           THEN 'gdrive://sample-' || (asset.metadata->>'ordinal')
                           ELSE 'gdrive://p129-' || %s || '-' || asset.id::text END,
                      'available',asset.sha256,asset.size_bytes,now(),%s,
                      jsonb_build_object('p129_acceptance',%s,'synthetic',NOT (asset.metadata->>'real_sample')::boolean),
                      CASE WHEN (asset.metadata->>'real_sample')::boolean THEN NULL ELSE now() END,
                      jsonb_build_object('seeded',true)
               FROM football_brief.assets asset
               WHERE asset.metadata->>'p129_acceptance'=%s""",
            (acceptance_key, actor, acceptance_key, acceptance_key),
        )
    return sample_ids


def _setwise_counts(database: Database, *, acceptance_key: str) -> dict[str, int]:
    with database.connection() as conn:
        return dict(
            conn.execute(
                """SELECT
                       count(DISTINCT asset.id)::int AS assets,
                       count(location.id)::int AS locations,
                       count(*) FILTER (WHERE location.provider='local')::int AS local_locations,
                       count(*) FILTER (WHERE location.provider='google_drive')::int AS drive_locations,
                       count(*) FILTER (
                         WHERE location.sha256<>asset.sha256
                            OR COALESCE(location.size_bytes,-1)<>COALESCE(asset.size_bytes,-1)
                       )::int AS canonical_mismatches,
                       count(*) FILTER (WHERE location.provider NOT IN ('local','google_drive'))::int AS unsupported_providers,
                       count(*) FILTER (WHERE asset.sha256<>asset.metadata->>'original_sha256')::int AS identity_changes
                   FROM football_brief.assets asset
                   JOIN football_brief.asset_storage_locations location ON location.asset_id=asset.id
                   WHERE asset.metadata->>'p129_acceptance'=%s""",
                (acceptance_key,),
            ).fetchone()
        )


def _duplicate_probe(database: Database, *, asset_id: UUID, actor: str) -> int:
    with database.transaction() as conn:
        before = int(
            conn.execute(
                "SELECT count(*)::int AS value FROM football_brief.asset_storage_locations WHERE asset_id=%s",
                (asset_id,),
            ).fetchone()["value"]
        )
        row = conn.execute(
            "SELECT * FROM football_brief.asset_storage_locations WHERE asset_id=%s ORDER BY provider LIMIT 1",
            (asset_id,),
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.asset_storage_locations
               (asset_id,provider,locator,status,sha256,size_bytes,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (asset_id, row["provider"], row["locator"], row["status"], row["sha256"], row["size_bytes"], actor),
        )
        after = int(
            conn.execute(
                "SELECT count(*)::int AS value FROM football_brief.asset_storage_locations WHERE asset_id=%s",
                (asset_id,),
            ).fetchone()["value"]
        )
    return after - before


def run_acceptance(
    *,
    assets: int = 50_000,
    locations: int = 100_000,
    acceptance_key: str | None = None,
    actor: str = "local-admin",
) -> dict[str, Any]:
    if not 3 <= assets <= 1_000_000:
        raise ValueError("assets must be between 3 and 1,000,000")
    if locations != assets * 2:
        raise ValueError("locations must equal exactly two per asset")
    key = acceptance_key or _key()
    timings: dict[str, float] = {}
    root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).expanduser().resolve()
    sample_root = root / "p129" / key
    sample_root.mkdir(parents=True, exist_ok=True)
    expected_available = b"p129 available canonical sample\n"
    expected_mismatch = b"p129 expected mismatch sample\n"
    expected_recovery = b"p129 Drive recovery canonical sample\n"
    local_paths = [
        sample_root / "available.bin",
        sample_root / "mismatch.bin",
        sample_root / "missing.bin",
    ]
    local_paths[0].write_bytes(expected_available)
    local_paths[1].write_bytes(b"different bytes that must fail canonical verification\n")
    local_paths[2].unlink(missing_ok=True)
    samples = [expected_available, expected_mismatch, expected_recovery]
    fake_drive = FakeDrive({f"sample-{index}": payload for index, payload in enumerate(samples, start=1)})

    database = Database(get_database_settings())
    database.open(require_schema=True)
    acceptance_id: UUID | None = None
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            if operator is None:
                raise RuntimeError("storage acceptance onboarding is incomplete")
            acceptance = conn.execute(
                """INSERT INTO football_brief.storage_scale_acceptance_runs
                   (acceptance_key,status,requested_assets,requested_locations,requested_by,environment)
                   VALUES (%s,'running',%s,%s,%s,%s::jsonb) RETURNING id""",
                (
                    key,
                    assets,
                    locations,
                    actor,
                    _json({
                        "hostname": socket.gethostname(),
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                        "git_sha": os.getenv("GITHUB_SHA") or os.getenv("OPS_GIT_SHA"),
                        "canonical_database": "postgresql",
                        "providers": ["local", "google_drive"],
                        "external_drive_network": False,
                    }),
                ),
            ).fetchone()
            acceptance_id = UUID(str(acceptance["id"]))

        sample_ids = _timed(
            timings,
            "seed_assets_and_locations",
            _seed,
            database,
            acceptance_key=key,
            assets=assets,
            samples=samples,
            local_paths=local_paths,
            actor=actor,
        )
        setwise = _timed(timings, "setwise_reconciliation", _setwise_counts, database, acceptance_key=key)
        duplicate_delta = _timed(timings, "duplicate_probe", _duplicate_probe, database,
                                 asset_id=sample_ids[0], actor=actor)

        storage = CampaignStorageService(database, drive=fake_drive)
        local_result = _timed(
            timings,
            "real_local_reconciliation",
            storage.reconcile,
            actor=actor,
            provider="local",
            strict_drive_download=False,
            limit=3,
        )
        drive_result = _timed(
            timings,
            "real_drive_reconciliation",
            storage.reconcile,
            actor=actor,
            provider="google_drive",
            strict_drive_download=True,
            limit=3,
        )
        recovery = CampaignStorageRecoveryService(database, drive=fake_drive)
        recovered = _timed(
            timings,
            "recover_missing_local",
            recovery.recover_missing_local,
            asset_id=sample_ids[2],
            actor=actor,
            destination=local_paths[2],
        )
        if local_paths[2].read_bytes() != expected_recovery:
            raise RuntimeError("recovered local bytes do not match canonical Drive bytes")

        metadata_calls_before = fake_drive.metadata_calls
        fake_drive.outage = True
        outage_result = _timed(
            timings,
            "drive_outage_local_reconciliation",
            storage.reconcile,
            actor=actor,
            provider="local",
            strict_drive_download=False,
            limit=1,
        )
        drive_outage_local_failures = int(fake_drive.metadata_calls != metadata_calls_before)
        fake_drive.outage = False

        mismatches = int(local_result["counts"]["mismatch"])
        missing = int(local_result["counts"]["missing"])
        recovered_count = int(bool(recovered["ok"]))
        canonical_identity_changes = int(setwise["identity_changes"])
        passed = (
            int(setwise["assets"]) == assets
            and int(setwise["locations"]) == locations
            and int(setwise["local_locations"]) == assets
            and int(setwise["drive_locations"]) == assets
            and int(setwise["canonical_mismatches"]) == 0
            and int(setwise["unsupported_providers"]) == 0
            and duplicate_delta == 0
            and mismatches >= 1
            and missing >= 1
            and recovered_count >= 1
            and canonical_identity_changes == 0
            and drive_outage_local_failures == 0
            and drive_result["counts"]["available"] == 3
            and outage_result["counts"]["checked"] == 1
        )
        counters = {
            **setwise,
            "duplicate_delta": duplicate_delta,
            "local_reconciliation": local_result["counts"],
            "drive_reconciliation": drive_result["counts"],
            "recovery_download_calls": fake_drive.download_calls,
            "outage_local_reconciliation": outage_result["counts"],
        }
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.storage_scale_acceptance_runs
                   SET status=%s,retained_assets=%s,retained_locations=%s,
                       duplicate_locations=%s,mismatches_detected=%s,missing_detected=%s,
                       recovered_local_copies=%s,canonical_identity_changes=%s,
                       drive_outage_local_failures=%s,timings_ms=%s::jsonb,counters=%s::jsonb,
                       error=%s::jsonb,completed_at=now()
                   WHERE id=%s""",
                (
                    "passed" if passed else "failed",
                    setwise["assets"],
                    setwise["locations"],
                    duplicate_delta,
                    mismatches,
                    missing,
                    recovered_count,
                    canonical_identity_changes,
                    drive_outage_local_failures,
                    _json(timings),
                    _json(counters),
                    _json({}) if passed else _json({"reason": "storage_acceptance_mismatch"}),
                    acceptance_id,
                ),
            )
        if not passed:
            raise RuntimeError(f"storage acceptance failed: {counters}")
        return {
            "ok": True,
            "kind": "p129_storage_scale_acceptance",
            "acceptance_key": key,
            "assets": assets,
            "locations": locations,
            "timings_ms": timings,
            "counters": counters,
        }
    except Exception as exc:
        if acceptance_id is not None:
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.storage_scale_acceptance_runs
                       SET status='failed',error=%s::jsonb,timings_ms=%s::jsonb,completed_at=now()
                       WHERE id=%s AND status='running'""",
                    (_json({"type": type(exc).__name__, "message": str(exc)}), _json(timings), acceptance_id),
                )
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P129 storage scale and recovery acceptance")
    parser.add_argument("--assets", type=int, default=50_000)
    parser.add_argument("--locations", type=int, default=100_000)
    parser.add_argument("--acceptance-key")
    args = parser.parse_args()
    print(_json(run_acceptance(
        assets=args.assets,
        locations=args.locations,
        acceptance_key=args.acceptance_key,
    )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
