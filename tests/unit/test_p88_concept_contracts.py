from pathlib import Path
from uuid import uuid4

import pytest

from src.application.concepts.adapters import (
    ConceptAdapterError,
    DeterministicConceptAdapter,
    LocalHttpConceptAdapter,
    build_slots,
)
from src.application.concepts.models import CandidateDraft, ProductionRoute, RiskLevel
from src.application.concepts.scoring import (
    concept_fingerprint,
    find_duplicate,
    score_candidate,
    semantic_tokens,
)
from src.application.concepts.service import balance_candidates


ROOT = Path(__file__).resolve().parents[2]


def context() -> dict:
    return {
        "brand_name": "Ocean Facts",
        "niche": "marine education",
        "audience": {"age": "18-34"},
        "tone": "clear and factual",
        "content_restrictions": {"avoid": ["graphic injury"]},
        "reference_patterns": [],
        "performance_signals": [],
        "brand_profile_id": "11111111-1111-1111-1111-111111111111",
        "brand_profile_version": 1,
    }


def draft(*, risk: RiskLevel = RiskLevel.LOW) -> CandidateDraft:
    return CandidateDraft(
        title="How octopus arms sense the world",
        hook="An octopus arm can react before the brain does.",
        concept=(
            "Explain the distributed sensing system in an octopus arm through three "
            "evidence-led beats and finish with a practical conservation takeaway."
        ),
        format="vertical_short",
        pillar="education",
        rationale="The concept gives the audience a specific factual question and a clear payoff.",
        source_requirements=["Primary anatomy source", "Independent corroborating source"],
        required_research=["Verify the distributed-neuron claim"],
        factual_risk=risk,
        production_complexity=RiskLevel.LOW,
        estimated_cost_usd=0,
        recommended_route=ProductionRoute.LOCAL,
    )


def test_fixed_seed_generation_is_deterministic_and_distribution_bound() -> None:
    slots = build_slots(
        format_mix={"vertical_short": 2, "carousel": 2},
        pillar_targets={"education": 2, "conservation": 2},
        seed=41,
    )
    adapter = DeterministicConceptAdapter()
    first = adapter.generate(context=context(), slots=slots, seed=41)
    second = adapter.generate(context=context(), slots=slots, seed=41)

    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
    assert sorted(item.format for item in first) == ["carousel", "carousel", "vertical_short", "vertical_short"]
    assert sorted(item.pillar for item in first) == ["conservation", "conservation", "education", "education"]
    assert all(item.required_research for item in first)
    assert all(item.source_requirements for item in first)


def test_local_adapter_rejects_non_loopback_endpoints() -> None:
    with pytest.raises(ConceptAdapterError, match="localhost"):
        LocalHttpConceptAdapter(endpoint="https://paid-provider.example", model_id="remote-model")


def test_policy_risk_is_explainable_and_reduces_total_score() -> None:
    low = score_candidate(draft(risk=RiskLevel.LOW), duplicate=None, context=context())
    high = score_candidate(draft(risk=RiskLevel.HIGH), duplicate=None, context=context())

    assert high.policy_risk > low.policy_risk
    assert high.total < low.total
    assert high.evidence["formula"]["inverse_policy_risk"] == 0.10
    assert high.evidence["policy_risk"]


def test_exact_and_semantic_duplicates_return_matching_evidence() -> None:
    candidate = draft()
    fingerprint = concept_fingerprint(
        title=candidate.title,
        hook=candidate.hook,
        concept=candidate.concept,
    )
    tokens = semantic_tokens(candidate.title, candidate.hook, candidate.concept)
    content_id = uuid4()
    exact = find_duplicate(
        fingerprint=fingerprint,
        tokens=tokens,
        historical_rows=[
            {
                "id": content_id,
                "title": candidate.title,
                "concept_fingerprint": fingerprint,
                "semantic_tokens": tokens,
            }
        ],
    )
    assert exact is not None
    assert exact.kind == "exact"
    assert exact.content_id == str(content_id)


def test_balancer_respects_exact_format_and_pillar_margins() -> None:
    candidates = []
    combinations = [
        ("vertical_short", "education"),
        ("vertical_short", "conservation"),
        ("carousel", "education"),
        ("carousel", "conservation"),
    ]
    for ordinal, (format_name, pillar) in enumerate(combinations, start=1):
        candidates.append(
            {
                "id": uuid4(),
                "ordinal": ordinal,
                "format": format_name,
                "pillar": pillar,
                "total_score": 90 - ordinal,
            }
        )

    selected, gaps = balance_candidates(
        candidates,
        selected_count=4,
        format_mix={"vertical_short": 2, "carousel": 2},
        pillar_targets={"education": 2, "conservation": 2},
    )
    assert len(selected) == 4
    assert gaps["missing_count"] == 0
    assert gaps["format_gaps"] == {}
    assert gaps["pillar_gaps"] == {}


def test_migrations_runtime_and_service_preserve_review_only_local_boundary() -> None:
    migration = (ROOT / "migrations" / "0034_local_concept_generation.sql").read_text(encoding="utf-8")
    hardening = (ROOT / "migrations" / "0036_concept_slate_integrity.sql").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "concepts" / "safe_service.py").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "operator_api" / "concepts_runtime.py").read_text(encoding="utf-8")
    factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(encoding="utf-8")

    assert "paid_provider_allowed boolean NOT NULL DEFAULT false" in migration
    assert "Candidate generation never inserts directly" in migration
    assert "DROP CONSTRAINT IF EXISTS concept_candidates_batch_id_concept_fingerprint_key" in hardening
    assert "Concept slate cannot be applied until every item" in hardening
    assert "reference_approval_gates" in service
    assert "performance_observations" in service
    assert "monthly_plan_not_draft" in service
    assert "admin_required" in runtime
    assert "install_concept_routes" in factory
