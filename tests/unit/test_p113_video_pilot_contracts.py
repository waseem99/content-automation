from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from src.application.video_pilot.models import DistributionScope, ModelUsePreflightRequest
from src.application.video_pilot.policy import evaluate_model_policy
from src.application.video_pilot.reporting import compile_pilot_report
from src.application.video_pilot.validation import PilotSnapshotValidationError, assert_snapshot_safe


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = [
    ROOT / "migrations" / "0096_p113_video_pilot_calibration.sql",
    ROOT / "migrations" / "0097_p113_model_policy_versioning.sql",
    ROOT / "migrations" / "0098_p113_pilot_video_grouping.sql",
]
RUNTIME = ROOT / "src" / "operator_api" / "video_pilot_runtime.py"
FACTORY = ROOT / "src" / "operator_api" / "runtime_factory.py"
POLICY_ONBOARDING = ROOT / "src" / "operations" / "p113_model_policy_onboarding.py"
INITIALIZER = ROOT / "src" / "operations" / "p113_pilot_initialize.py"
PLAN = ROOT / "config" / "p113-pilot-plan.example.json"
CONFIG = ROOT / "config" / "local.env.example"
DEPLOY = ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1"
CAPTURE = ROOT / "scripts" / "windows" / "capture_p113_hardware_snapshot.ps1"
INITIALIZE_PS = ROOT / "scripts" / "windows" / "initialize_p113_pilot.ps1"


def policy(**overrides):
    value = {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "version": 1,
        "evidence_digest": "a" * 64,
        "commercial_use_allowed": True,
        "allowed_use_scopes": ["internal", "territory_limited", "global_public"],
        "allowed_territories": ["worldwide"],
        "prohibited_territories": [],
        "requires_written_clearance": False,
    }
    value.update(overrides)
    return value


def preflight(**overrides):
    value = {
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "distribution_scope": DistributionScope.GLOBAL_PUBLIC,
        "release_territories": (),
    }
    value.update(overrides)
    return ModelUsePreflightRequest(**value)


def test_wan_global_public_policy_is_eligible_for_pilot_preflight() -> None:
    result = evaluate_model_policy(policy(), preflight())
    assert result["accepted"] is True
    assert result["rejection_reasons"] == []


def test_hunyuan_global_public_is_rejected_by_active_policy() -> None:
    hunyuan = policy(
        provider_key="tencent-hunyuan",
        model_key="HunyuanVideo-1.5-480p-I2V-Step-Distilled",
        allowed_use_scopes=["internal", "territory_limited"],
        prohibited_territories=["European Union", "United Kingdom", "South Korea"],
        requires_written_clearance=True,
    )
    result = evaluate_model_policy(
        hunyuan,
        preflight(provider_key=hunyuan["provider_key"], model_key=hunyuan["model_key"]),
    )
    assert result["accepted"] is False
    assert "distribution_scope_not_allowed" in result["rejection_reasons"]
    assert "global_public_distribution_reaches_prohibited_territories" in result["rejection_reasons"]
    assert result["clearance_process"] == "activate_a_reviewed_child_policy_version"


def test_hunyuan_territory_preflight_rejects_prohibited_region_and_accepts_allowed_region() -> None:
    hunyuan = policy(
        provider_key="tencent-hunyuan",
        model_key="HunyuanVideo-1.5-480p-I2V-Step-Distilled",
        allowed_use_scopes=["internal", "territory_limited"],
        prohibited_territories=["European Union", "United Kingdom", "South Korea"],
        requires_written_clearance=True,
    )
    blocked = evaluate_model_policy(
        hunyuan,
        preflight(
            provider_key=hunyuan["provider_key"],
            model_key=hunyuan["model_key"],
            distribution_scope=DistributionScope.TERRITORY_LIMITED,
            release_territories=("United Kingdom",),
        ),
    )
    allowed = evaluate_model_policy(
        hunyuan,
        preflight(
            provider_key=hunyuan["provider_key"],
            model_key=hunyuan["model_key"],
            distribution_scope=DistributionScope.TERRITORY_LIMITED,
            release_territories=("Pakistan",),
        ),
    )
    assert blocked["accepted"] is False
    assert blocked["prohibited_territory_matches"] == ["united_kingdom"]
    assert allowed["accepted"] is True


def test_clearance_cannot_be_supplied_as_an_ad_hoc_attempt_field() -> None:
    source = (ROOT / "src" / "application" / "video_pilot" / "models.py").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "video_pilot" / "service.py").read_text(encoding="utf-8")
    assert "written_clearance_reference" not in source
    assert "written_clearance_reference" not in service
    assert "activate_a_reviewed_child_policy_version" in (
        ROOT / "src" / "application" / "video_pilot" / "policy.py"
    ).read_text(encoding="utf-8")


def test_hardware_snapshots_reject_sensitive_fields_recursively() -> None:
    assert_snapshot_safe({"gpu": {"name": "RTX", "temperature": 70}})
    for payload in (
        {"api_token": "not-allowed"},
        {"nested": {"operatorKey": "not-allowed"}},
        {"rows": [{"cookie": "not-allowed"}]},
    ):
        with pytest.raises(PilotSnapshotValidationError):
            assert_snapshot_safe(payload)


def test_report_counts_complete_pilot_videos_not_individual_accepted_clips() -> None:
    now = datetime.now(timezone.utc)
    item_a = UUID("00000000-0000-0000-0000-000000000010")
    item_b = UUID("00000000-0000-0000-0000-000000000020")
    case_a1 = UUID("00000000-0000-0000-0000-000000000011")
    case_a2 = UUID("00000000-0000-0000-0000-000000000012")
    case_b1 = UUID("00000000-0000-0000-0000-000000000021")
    attempts = []
    reviews = []
    for index, case_id in enumerate((case_a1, case_a2, case_b1), start=1):
        attempt_id = UUID(f"00000000-0000-0000-0000-{index:012d}")
        attempts.append(
            {
                "id": attempt_id,
                "pilot_case_id": case_id,
                "model_policy_id": UUID("00000000-0000-0000-0000-000000000001"),
                "status": "succeeded",
                "started_at": now,
                "completed_at": now + timedelta(minutes=index),
                "gpu_active_ms": 60000,
                "wall_clock_ms": 90000,
                "external_cost_usd": Decimal("0"),
            }
        )
        reviews.append(
            {
                "pilot_attempt_id": attempt_id,
                "decision": "accepted",
                "motion_quality": Decimal("80"),
                "reference_consistency": Decimal("80"),
                "artifact_control": Decimal("80"),
                "composition_quality": Decimal("80"),
                "defect_tags": [],
            }
        )
    detail = {
        "run": {
            "id": UUID("00000000-0000-0000-0000-000000000100"),
            "status": "running",
            "target_videos": 2,
            "target_attempts": 3,
        },
        "items": [
            {"id": item_a, "status": "completed"},
            {"id": item_b, "status": "production"},
        ],
        "cases": [
            {"id": case_a1, "pilot_item_id": item_a, "target_duration_seconds": Decimal("4")},
            {"id": case_a2, "pilot_item_id": item_a, "target_duration_seconds": Decimal("5")},
            {"id": case_b1, "pilot_item_id": item_b, "target_duration_seconds": Decimal("6")},
            {"id": UUID("00000000-0000-0000-0000-000000000022"), "pilot_item_id": item_b, "target_duration_seconds": Decimal("4")},
        ],
        "attempts": attempts,
        "reviews": reviews,
    }
    report = compile_pilot_report(detail)
    assert report["actuals"]["accepted_clips"] == 3
    assert report["actuals"]["completed_videos"] == 1
    assert report["acceptance_ready"] is False
    assert "completed_video_target_not_met" in report["insufficiency_reasons"]


def test_p113_schema_is_forward_only_versioned_and_measured() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)
    assert "DROP TABLE" not in source
    assert "TRUNCATE" not in source
    assert "video_model_use_policies" in source
    assert "video_pilot_items" in source
    assert "video_pilot_attempts" in source
    assert "gpu_active_ms" in source
    assert "peak_vram_mib" in source
    assert "average_gpu_power_w" in source
    assert "workflow_sha256" in source
    assert "checkpoint_sha256" in source
    assert "Terminal pilot attempts are immutable" in source
    assert "create a child version" in source


def test_routes_and_runtime_register_authenticated_pilot_workflow() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    factory = FACTORY.read_text(encoding="utf-8")
    for route in (
        "/video-pilot/model-use-preflight",
        "/video-pilot/runs",
        "/video-pilot/runs/{run_id}/items",
        "/video-pilot/runs/{run_id}/cases",
        "/video-pilot/cases/{case_id}/attempts",
        "/video-pilot/attempts/{attempt_id}/complete",
        "/video-pilot/attempts/{attempt_id}/reviews",
        "/video-pilot/runs/{run_id}/report",
    ):
        assert route in runtime
    assert "OperatorIdentity = Depends(authenticate)" in runtime
    assert "install_video_pilot_routes" in factory


def test_model_policy_onboarding_is_idempotent_and_global_public_defaults_to_wan() -> None:
    source = POLICY_ONBOARDING.read_text(encoding="utf-8")
    assert '"model_key": "Wan2.2-TI2V-5B"' in source
    assert '"global_public_default_candidate": True' in source
    assert '"model_key": "HunyuanVideo-1.5-480p-I2V-Step-Distilled"' in source
    assert '"prohibited_territories": ["European Union", "United Kingdom", "South Korea"]' in source
    assert '"global_public_default_candidate": False' in source
    assert "evidence_digest" in source
    assert "reused" in source


def test_pilot_plan_has_three_videos_six_shot_classes_and_no_paid_activation() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["target_videos"] == 3
    assert plan["target_attempts"] == 30
    assert len(plan["items"]) == 3
    cases = [case for item in plan["items"] for case in item["cases"]]
    assert {case["shot_class"] for case in cases} == {
        "easy_motion",
        "people_animals",
        "product",
        "map_diagram",
        "transition",
        "hero",
    }
    assert plan["baseline_assumptions"]["throughput_claim_status"] == "unmeasured"
    assert plan["baseline_assumptions"]["external_paid_generation_enabled"] is False
    assert plan["baseline_assumptions"]["automatic_public_publishing"] is False


def test_windows_upgrade_preserves_secrets_and_keeps_current_schema_head() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")
    capture = CAPTURE.read_text(encoding="utf-8")
    initialize = INITIALIZE_PS.read_text(encoding="utf-8")
    initializer = INITIALIZER.read_text(encoding="utf-8")
    config_heads = [
        line.split("=", 1)[1]
        for line in config.splitlines()
        if line.startswith("OPS_MIGRATION_HEAD=")
    ]
    assert len(config_heads) == 1
    migration_head = config_heads[0]
    assert int(migration_head.split("_", 1)[0]) >= 98
    assert (ROOT / "migrations" / migration_head).is_file()
    assert f'$values["OPS_MIGRATION_HEAD"] = "{migration_head}"' in deploy
    assert "p113_model_policy_onboarding" in deploy
    assert "OPERATOR_API_KEYS_JSON" not in deploy
    assert "computer_name" not in capture
    assert '"uuid"' not in capture.lower()
    assert "uuid =" not in capture.lower()
    assert "environment variables and credentials are omitted" in capture
    assert "p113_pilot_initialize" in initialize
    assert "operator-keys.json" not in initialize
    assert '"paid_generation_enabled": False' in initializer
    assert '"automatic_public_publishing": False' in initializer
