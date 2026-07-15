from __future__ import annotations

import json
from pathlib import Path

from src.p68_batch_preflight import DEPLOY_KEYS, SUBMIT_KEYS, build_batch_preflight


def test_preflight_reports_ready_blocked_authored_and_missing_config(tmp_path: Path) -> None:
    pilots, artifacts = tmp_path / "pilots", tmp_path / "artifacts"
    pilot = pilots / "rawr-blind-spot"
    pilot.mkdir(parents=True)
    (pilot / "content-plan.json").write_text(
        json.dumps(
            {
                "pilot_id": "rawr-blind-spot",
                "shots": [
                    {"shot_id": "S01", "story_stage": "hook"},
                    {"shot_id": "S02", "story_stage": "setup"},
                    {"shot_id": "S07", "story_stage": "reveal"},
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = artifacts / "gold" / "rawr-blind-spot" / "assets" / "asset-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {"shot_id": "S01", "path": "/s01.png", "source": "derived_shot_asset"},
                    {"shot_id": "S02", "path": "/master.png", "source": "continuity_master_preview_fallback"},
                    {"shot_id": "S07", "path": "/master.png", "source": "continuity_master_preview_fallback"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = build_batch_preflight(pilots, artifacts, environ={})
    row = result["pilots"][0]

    assert [item["shot_id"] for item in row["ready"]] == ["S01"]
    assert [item["shot_id"] for item in row["blocked"]] == ["S07"]
    assert row["authored_science_shot_ids"] == ["S02"]
    assert result["ready_variant_count"] == 2
    assert result["missing_worker_deploy_keys"] == list(DEPLOY_KEYS)
    assert result["missing_application_submit_keys"] == list(SUBMIT_KEYS)
    assert "--shots S01" in row["submit_command"]


def test_preflight_never_serializes_environment_values(tmp_path: Path) -> None:
    pilots, artifacts = tmp_path / "pilots", tmp_path / "artifacts"
    pilots.mkdir()
    env = {key: f"secret-{key}" for key in (*DEPLOY_KEYS, *SUBMIT_KEYS)}

    result = build_batch_preflight(pilots, artifacts, environ=env)

    serialized = json.dumps(result)
    assert "secret-" not in serialized
    assert result["worker_deploy_ready"] is True
    assert result["application_submit_ready"] is True
