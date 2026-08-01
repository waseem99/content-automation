from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_autopilot_review_preserves_legacy_independence_gate() -> None:
    legacy = (ROOT / "migrations" / "0042_script_review_evidence.sql").read_text(encoding="utf-8")
    patch = (
        ROOT
        / "src"
        / "application"
        / "pre_generation"
        / "final_runtime_patch.py"
    ).read_text(encoding="utf-8")

    assert "Independent script review is required" in legacy
    assert "pre-generation-autopilot-reviewer" in patch
    assert "non_login_autopilot_identity" in patch
    assert "orchestration_worker" in patch
    assert "independent_reviewer" in patch
    assert "PreGenerationService._script_approval = _automatic_script_approval" in patch
    assert "DROP TRIGGER script_review_decision_valid" not in patch
    assert "CREATE OR REPLACE FUNCTION football_brief.validate_script_review_decision" not in patch


def test_autopilot_reviewer_has_no_login_key_creation_path() -> None:
    patch = (
        ROOT
        / "src"
        / "application"
        / "pre_generation"
        / "final_runtime_patch.py"
    ).read_text(encoding="utf-8")

    assert "operator_users" in patch
    assert "operator_user_roles" in patch
    assert "api_key" not in patch
    assert "operator_api_keys" not in patch
