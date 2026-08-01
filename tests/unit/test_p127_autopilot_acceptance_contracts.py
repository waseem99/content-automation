from __future__ import annotations

from pathlib import Path

from src.application.pre_generation import PreGenerationService
from src.operations.autopilot_acceptance import run_acceptance


ROOT = Path(__file__).resolve().parents[2]


def test_acceptance_runner_and_campaign_scoped_claim_are_available() -> None:
    assert callable(run_acceptance)
    assert "campaign_id" in PreGenerationService.claim.__annotations__


def test_acceptance_migration_requires_95_percent_and_reproducibility() -> None:
    migration = (
        ROOT / "migrations" / "0104_p127_autopilot_scale_acceptance.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE football_brief.autopilot_acceptance_runs" in migration
    assert "automation_rate >= 0.95" in migration
    assert "human_exception_items = 0" in migration
    assert "individual_page_approvals = 0" in migration
    assert "reproducible_ready_decisions >= expected_ready" in migration


def test_runner_uses_real_content_script_and_autopilot_services() -> None:
    source = (ROOT / "src" / "operations" / "autopilot_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert "ValidatedCampaignService" in source
    assert "ValidatedPreGenerationService" in source
    assert "ScriptReviewService" in source
    assert "CampaignItemsAddRequest(items=payload)" in source
    assert "max_steps=1" in source
    assert "max_steps=12" in source
    assert "supported_items: int = 950" in source
    assert "items: int = 1_000" in source
    assert "automatic_policy_decision" in source
    assert "pre-generation-autopilot-reviewer" in source
    assert '"individual_page_approvals": 0' in source
    assert '"final_video_generation": False' in source
    assert '"public_publishing": False' in source


def test_campaign_scoped_claim_preserves_original_worker_behavior() -> None:
    patch = (
        ROOT
        / "src"
        / "application"
        / "pre_generation"
        / "campaign_claim_patch.py"
    ).read_text(encoding="utf-8")
    initializer = (
        ROOT / "src" / "application" / "pre_generation" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "if campaign_id is None" in patch
    assert "return _ORIGINAL_CLAIM" in patch
    assert "AND campaign.id=%s" in patch
    assert "FOR UPDATE OF run SKIP LOCKED" in patch
    assert "install_campaign_scoped_claim_patch()" in initializer


def test_acceptance_runner_does_not_render_or_publish() -> None:
    source = (ROOT / "src" / "operations" / "autopilot_acceptance.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "GenerationJobService",
        "request.urlopen",
        "httpx",
        "OpenAI(",
        "publish_manifest",
        "platform_delivery",
    )
    assert not any(value in source for value in forbidden)
