from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify() -> dict[str, Any]:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            row = conn.execute(
                """SELECT e.*,gj.status AS job_status,gj.output_payload,gj.actual_cost_usd,
                          ga.status AS attempt_status,a.asset_type,a.lifecycle_status,
                          a.storage_uri,a.sha256 AS asset_sha256,a.mime_type,a.size_bytes,
                          a.metadata AS asset_metadata
                   FROM football_brief.local_video_executions e
                   JOIN football_brief.generation_jobs gj ON gj.id=e.generation_job_id
                   JOIN football_brief.generation_job_attempts ga ON ga.id=e.generation_attempt_id
                   LEFT JOIN football_brief.assets a ON a.id=e.output_asset_id
                   WHERE e.status='succeeded'
                   ORDER BY e.completed_at DESC,e.id DESC
                   LIMIT 1"""
            ).fetchone()
    finally:
        database.close()
    if not row:
        raise RuntimeError("no succeeded local video execution exists")

    record = dict(row)
    metadata = dict(record.get("asset_metadata") or {})
    output_payload = dict(record.get("output_payload") or {})
    storage_path = metadata.get("storage_path") or output_payload.get("storage_path")
    if not storage_path:
        raise RuntimeError("local video asset has no canonical storage path")
    path = Path(str(storage_path)).resolve()

    checks = {
        "execution_succeeded": record["status"] == "succeeded",
        "job_succeeded": record["job_status"] == "succeeded",
        "attempt_succeeded": record["attempt_status"] == "succeeded",
        "output_asset_present": record.get("output_asset_id") is not None,
        "asset_is_video": record.get("asset_type") == "video",
        "asset_internal_only": record.get("lifecycle_status") == "internal_only",
        "asset_is_mp4": record.get("mime_type") == "video/mp4" and path.suffix.lower() == ".mp4",
        "file_exists": path.is_file(),
        "zero_execution_cost": float(record.get("external_cost_usd") or 0) == 0,
        "zero_job_cost": float(record.get("actual_cost_usd") or 0) == 0,
        "review_pending": metadata.get("review_status") == "pending",
        "human_review_required": metadata.get("human_content_review_required") is True,
        "automatic_approval_disabled": metadata.get("automatic_approval") is False,
        "automatic_publishing_disabled": output_payload.get("automatic_publishing") is False,
    }
    if path.is_file():
        checks["size_matches"] = path.stat().st_size == int(record["size_bytes"])
        checks["sha256_matches"] = _sha256(path) == str(record["asset_sha256"])
    else:
        checks["size_matches"] = False
        checks["sha256_matches"] = False

    failed = sorted(key for key, value in checks.items() if not value)
    return {
        "ok": not failed,
        "kind": "p114_first_local_mp4_evidence",
        "generation_job_id": str(record["generation_job_id"]),
        "generation_attempt_id": str(record["generation_attempt_id"]),
        "execution_id": str(record["id"]),
        "provider_request_id": record.get("provider_request_id"),
        "output_asset_id": str(record["output_asset_id"]),
        "storage_path": str(path),
        "storage_uri": record.get("storage_uri"),
        "sha256": record.get("asset_sha256"),
        "size_bytes": int(record["size_bytes"]),
        "wall_clock_ms": record.get("wall_clock_ms"),
        "gpu_active_ms": record.get("gpu_active_ms"),
        "external_cost_usd": float(record.get("external_cost_usd") or 0),
        "checks": checks,
        "failed_checks": failed,
        "human_review_still_required": True,
        "automatic_approval": False,
        "automatic_publishing": False,
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {
            "ok": False,
            "kind": "p114_first_local_mp4_evidence",
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
