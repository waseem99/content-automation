from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _asset_path(asset: dict[str, Any]) -> Path:
    artifact_root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).resolve()
    metadata = dict(asset.get("metadata") or {})
    explicit = metadata.get("storage_path")
    if explicit:
        path = Path(str(explicit)).resolve()
    else:
        uri = str(asset["storage_uri"])
        prefix = "local-artifact://"
        if not uri.startswith(prefix):
            raise RuntimeError("approved keyframe is not stored locally")
        path = (artifact_root / uri[len(prefix):]).resolve()
    if not path.is_file() or artifact_root not in path.parents:
        raise RuntimeError("approved keyframe path is missing or outside LOCAL_ARTIFACT_ROOT")
    return path


def locate() -> dict[str, Any]:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            row = conn.execute(
                """SELECT a.*,pc.id AS portfolio_content_id,vs.id AS visual_shot_id,
                          vc.id AS visual_candidate_id,vs.sequence
                   FROM football_brief.visual_shots vs
                   JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
                   JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
                   JOIN football_brief.visual_candidates vc ON vc.id=vs.selected_candidate_id
                   JOIN football_brief.assets a ON a.id=vc.asset_id
                   WHERE vs.status='approved' AND vc.status='selected'
                     AND a.asset_type='image' AND a.lifecycle_status='approved'
                   ORDER BY vs.updated_at DESC,vs.id
                   LIMIT 1"""
            ).fetchone()
    finally:
        database.close()
    if not row:
        return {
            "ok": False,
            "kind": "p114_latest_approved_keyframe",
            "reason": "no approved selected keyframe is available",
        }
    asset = dict(row)
    path = _asset_path(asset)
    return {
        "ok": True,
        "kind": "p114_latest_approved_keyframe",
        "asset_id": str(asset["id"]),
        "portfolio_content_id": str(asset["portfolio_content_id"]),
        "visual_shot_id": str(asset["visual_shot_id"]),
        "visual_candidate_id": str(asset["visual_candidate_id"]),
        "sequence": int(asset["sequence"]),
        "path": str(path),
        "sha256": str(asset["sha256"]),
        "storage_uri": str(asset["storage_uri"]),
    }


def main() -> int:
    try:
        result = locate()
    except Exception as exc:
        result = {
            "ok": False,
            "kind": "p114_latest_approved_keyframe",
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
