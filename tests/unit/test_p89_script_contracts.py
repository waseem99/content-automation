from pathlib import Path

import pytest

from src.application.scripts.adapters import (
    DeterministicScriptAdapter,
    LocalHttpScriptAdapter,
    ScriptAdapterError,
    estimated_duration_seconds,
    word_count,
)
from src.application.scripts.models import ClaimSupportStatus, ScriptGenerateRequest


ROOT = Path(__file__).resolve().parents[2]


def context() -> dict:
    return {
        "title": "How octopus arms sense the world",
        "concept": "Explain distributed sensing with evidence and a conservation takeaway.",
        "brand_name": "Ocean Facts",
        "tone": "clear factual narration",
        "audience": {"age": "18-34"},
        "content_restrictions": {"avoid": ["sensationalism"]},
        "brand_profile_id": "11111111-1111-1111-1111-111111111111",
    }


def request(seed: int = 17) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        platform="facebook",
        format="vertical_short",
        language="en-US",
        target_duration_seconds=60,
        words_per_minute=150,
        seed=seed,
    )


def test_deterministic_script_is_fixed_seed_duration_aware_and_claim_mapped() -> None:
    adapter = DeterministicScriptAdapter()
    first = adapter.generate(context=context(), configuration=request(17))
    second = adapter.generate(context=context(), configuration=request(17))

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert {section.section_key for section in first.sections} == {"hook", "body", "cta"}
    assert {scene.section_key for scene in first.scenes} == {"hook", "body", "cta"}
    assert {claim.section_key for claim in first.claims} == {"hook", "body"}
    assert all(claim.support_status == ClaimSupportStatus.NEEDS_SOURCE for claim in first.claims)
    assert first.sources == []
    assert first.claim_sources == []
    total_words = sum(word_count(section.text) for section in first.sections)
    total_duration = sum(
        estimated_duration_seconds(section.text, first.words_per_minute)
        for section in first.sections
    )
    assert 145 <= total_words <= 155
    assert 58 <= total_duration <= 62
    assert first.generation_evidence["claims_default_to_needs_source"] is True


def test_local_script_adapter_rejects_non_loopback_endpoints() -> None:
    with pytest.raises(ScriptAdapterError, match="localhost"):
        LocalHttpScriptAdapter(
            endpoint="https://paid-provider.example",
            model_id="remote-model",
        )


def test_schema_and_job_gate_are_fail_closed() -> None:
    schema = (ROOT / "migrations" / "0041_script_claim_source_schema.sql").read_text(encoding="utf-8")
    review = (ROOT / "migrations" / "0042_script_review_evidence.sql").read_text(encoding="utf-8")
    integrity = (ROOT / "migrations" / "0046_script_version_pointer_hardening.sql").read_text(encoding="utf-8")
    gate = (ROOT / "migrations" / "0044_script_downstream_job_gate.sql").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "scripts" / "service.py").read_text(encoding="utf-8")

    assert "CREATE TABLE football_brief.script_versions" in schema
    assert "CREATE TABLE football_brief.script_claims" in schema
    assert "CREATE TABLE football_brief.script_sources" in schema
    assert "CREATE TABLE football_brief.script_review_actions" in review
    assert "Stale script versions cannot be reviewed" in review
    assert "Unsupported factual claims block script approval" in integrity
    assert "Every final narration paragraph requires a claim mapping" in integrity
    assert "Submitted script versions are immutable" in integrity
    assert "Narration and preview jobs require an approved script and scene plan" in gate
    assert "script_version_id" in gate
    assert "_copy_children" in service
    assert "script_review_actions" in service
