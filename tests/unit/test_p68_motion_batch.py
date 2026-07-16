from __future__ import annotations

import json
from pathlib import Path

from src.p68_motion_batch import build_motion_batch_plan


ROOT = Path(__file__).resolve().parents[2]


def test_six_pilot_motion_inventory_is_complete_and_honest(tmp_path: Path) -> None:
    result = build_motion_batch_plan(ROOT / "p68-pilots", tmp_path, environ={})

    assert result["pilot_count"] == 6
    assert result["roster_complete"] is True
    assert result["inventory"]["total_shots"] == 36
    assert result["inventory"]["authored_science_shots"] == 7
    assert result["inventory"]["natural_motion_shots"] == 29
    assert result["inventory"]["natural_shots_blocked_on_keyframes"] == 29
    assert result["inventory"]["planned_generation_variants"] == 40
    assert result["next_gate"] == "create_shot_specific_keyframes"
    assert result["execution_allowed"] is False
    assert result["premium_provider_calls_allowed"] is False
    assert result["paid_provider_calls_made"] == 0
    assert result["vercel_deployment_required"] is False
    assert result["production_candidate_count"] == 0
    assert result["publish_allowed"] is False


def test_plan_records_presence_and_cost_without_serializing_secrets(tmp_path: Path) -> None:
    env = {
        "P68_RN_BASE_URL": "https://secret-worker.example",
        "P68_RN_GPU_HOURLY_USD": "1.25",
        "P68_RN_BEARER_TOKEN": "do-not-leak",
    }
    result = build_motion_batch_plan(ROOT / "p68-pilots", tmp_path, environ=env)
    rendered = json.dumps(result)

    assert result["configuration_presence"] == {
        "P68_RN_BASE_URL": True,
        "P68_RN_GPU_HOURLY_USD": True,
    }
    assert result["rn_configuration_ready"] is True
    assert result["estimated_rn_cost_usd"] == "7.5000"
    assert "secret-worker" not in rendered
    assert "do-not-leak" not in rendered
    assert result["execution_allowed"] is False  # no acceptable keyframes in tmp_path
