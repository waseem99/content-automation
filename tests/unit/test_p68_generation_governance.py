from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.p68_generation_governance import GenerationBudget, GenerationLedger, SpendDecision, TermsEvidence
from src.p68_video_provider import VideoGenerationRequest, VideoJob, VideoJobStatus


def terms() -> TermsEvidence:
    return TermsEvidence(
        provider="rn-comfyui-wan",
        model_id="wan2.2-ti2v-5b",
        license_type="Apache-2.0",
        license_url="https://example.test/license",
        terms_snapshot_sha256="a" * 64,
        commercial_use_allowed=True,
        modification_allowed=True,
        captured_at="2026-07-13T00:00:00Z",
    )


def generation_request(tmp_path: Path) -> VideoGenerationRequest:
    image = tmp_path / "input.png"
    image.write_bytes(b"input")
    return VideoGenerationRequest(
        pilot_id="pilot",
        shot_id="S01",
        input_image=image,
        prompt="Natural movement",
        negative_prompt="static",
        duration_seconds=5,
        seed=1,
    )


def test_budget_soft_and_hard_caps() -> None:
    budget = GenerationBudget()
    assert budget.decide(current_spend_usd=Decimal("1"), estimated_cost_usd=Decimal("2")) == SpendDecision.ALLOW
    assert budget.decide(current_spend_usd=Decimal("3"), estimated_cost_usd=Decimal("2")) == SpendDecision.NEEDS_APPROVAL
    assert budget.decide(current_spend_usd=Decimal("9"), estimated_cost_usd=Decimal("2")) == SpendDecision.STOP
    assert budget.decide(current_spend_usd=Decimal("0"), estimated_cost_usd=Decimal("1"), premium=True) == SpendDecision.NEEDS_APPROVAL


def test_ledger_is_idempotent_scrubs_secrets_and_reconciles_spend(tmp_path: Path) -> None:
    ledger = GenerationLedger(tmp_path / "ledger.json", "pilot")
    request = generation_request(tmp_path)
    request = VideoGenerationRequest(**{**request.__dict__, "metadata": {"access_token": "secret", "safe": "ok"}})
    job = VideoJob(
        provider="rn-comfyui-wan",
        provider_job_id="job-1",
        idempotency_key=request.idempotency_key,
        status=VideoJobStatus.QUEUED,
        submitted_at="2026-07-13T00:00:00Z",
        model_id=request.model_id,
    )
    first = ledger.record_submission(
        request=request,
        job=job,
        terms=terms(),
        estimated_cost_usd=Decimal("0.20"),
        budget_decision=SpendDecision.ALLOW,
    )
    second = ledger.record_submission(
        request=request,
        job=job,
        terms=terms(),
        estimated_cost_usd=Decimal("0.20"),
        budget_decision=SpendDecision.ALLOW,
    )
    assert first == second
    assert len(ledger.payload["jobs"]) == 1
    assert first["metadata"]["access_token"] == "[redacted]"
    assert ledger.committed_spend_usd == Decimal("0.2000")
    output = tmp_path / "clip.webm"
    output.write_bytes(b"video")
    ledger.record_completion(idempotency_key=request.idempotency_key, output_path=output, actual_cost_usd=Decimal("0.18"))
    assert ledger.spend_usd == Decimal("0.1800")
    assert ledger.committed_spend_usd == Decimal("0.1800")
    assert ledger.payload["publish_allowed"] is False


def test_ledger_refuses_unapproved_spend(tmp_path: Path) -> None:
    ledger = GenerationLedger(tmp_path / "ledger.json", "pilot")
    request = generation_request(tmp_path)
    job = VideoJob("provider", "job", request.idempotency_key, VideoJobStatus.QUEUED, "now", request.model_id)
    with pytest.raises(PermissionError):
        ledger.record_submission(
            request=request,
            job=job,
            terms=terms(),
            estimated_cost_usd=Decimal("5"),
            budget_decision=SpendDecision.NEEDS_APPROVAL,
        )
