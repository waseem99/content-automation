from __future__ import annotations

from datetime import date

import psycopg
import pytest

from src.application.concepts.adapters import DeterministicConceptAdapter, build_slots
from src.application.concepts.models import (
    CandidateReviewAction,
    ConceptBatchRequest,
    SlateApplyRequest,
    SlateBuildRequest,
    SlateScheduleItem,
)
from src.application.concepts.scoring import concept_fingerprint, semantic_key, semantic_tokens
from src.application.concepts.validated_service import ValidatedConceptGenerationService
from tests.integration.p88_concept_support import p88_database, p88_seeded


pytestmark = pytest.mark.integration


def batch_request(brand_id, *, count: int, seed: int = 81) -> ConceptBatchRequest:
    if count == 30:
        format_mix = {"vertical_short": 15, "carousel": 15}
        pillar_targets = {"education": 10, "conservation": 10, "myth": 10}
    elif count == 4:
        format_mix = {"vertical_short": 2, "carousel": 2}
        pillar_targets = {"education": 2, "conservation": 2}
    else:
        format_mix = {"vertical_short": count}
        pillar_targets = {"education": count}
    return ConceptBatchRequest(
        brand_id=brand_id,
        month_start=date(2026, 9, 1),
        candidate_count=count,
        format_mix=format_mix,
        pillar_targets=pillar_targets,
        seed=seed,
    )


def test_generating_thirty_candidates_is_review_only_and_deterministic(
    p88_database, p88_seeded
) -> None:
    service = ValidatedConceptGenerationService(p88_database)
    first = service.generate_batch(
        batch_request(p88_seeded["brand_one"], count=30, seed=20260901),
        actor=p88_seeded["producer"],
    )

    assert first["batch"]["candidate_count"] == 30
    assert first["batch"]["paid_provider_allowed"] is False
    assert len(first["candidates"]) == 30
    assert all(row["required_research"] for row in first["candidates"])
    assert all(row["source_requirements"] for row in first["candidates"])
    assert all(row["score_evidence"]["formula"] for row in first["candidates"])
    assert all(row["accepted_content_id"] is None for row in first["candidates"])

    with p88_database.connection() as conn:
        content_count = conn.execute(
            "SELECT count(*) AS count FROM football_brief.portfolio_content"
        ).fetchone()
    assert int(content_count["count"]) == 0

    second = service.generate_batch(
        batch_request(p88_seeded["brand_one"], count=30, seed=20260901),
        actor=p88_seeded["producer"],
    )
    assert [row["title"] for row in first["candidates"]] == [
        row["title"] for row in second["candidates"]
    ]
    assert [row["concept"] for row in first["candidates"]] == [
        row["concept"] for row in second["candidates"]
    ]


def test_exact_duplicate_is_retained_with_matching_content_id(
    p88_database, p88_seeded
) -> None:
    service = ValidatedConceptGenerationService(p88_database)
    context = service._load_context(p88_seeded["brand_one"])
    slots = build_slots(
        format_mix={"vertical_short": 1},
        pillar_targets={"education": 1},
        seed=7,
    )
    draft = DeterministicConceptAdapter().generate(context=context, slots=slots, seed=7)[0]
    fingerprint = concept_fingerprint(title=draft.title, hook=draft.hook, concept=draft.concept)
    tokens = semantic_tokens(draft.title, draft.hook, draft.concept)

    with p88_database.transaction() as conn:
        historical = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id, scheduled_for, title, concept, format, concept_fingerprint,
                semantic_key, stage, metadata, brand_profile_id)
               VALUES (%s, DATE '2026-09-01', %s, %s, %s, %s, %s, 'idea',
                       '{"seeded":true}'::jsonb, %s)
               RETURNING id""",
            (
                p88_seeded["plan_one"],
                draft.title,
                draft.concept,
                draft.format,
                fingerprint,
                semantic_key(tokens),
                p88_seeded["profile_one"],
            ),
        ).fetchone()

    result = service.generate_batch(
        batch_request(p88_seeded["brand_one"], count=1, seed=7),
        actor=p88_seeded["producer"],
    )
    candidate = result["candidates"][0]
    assert candidate["status"] == "duplicate_blocked"
    assert candidate["duplicate_kind"] == "exact"
    assert str(candidate["duplicate_content_id"]) == str(historical["id"])
    assert candidate["score_evidence"]["duplicate"]["content_id"] == str(historical["id"])


def test_shortlist_balance_approve_and_apply_is_manual_and_immutable(
    p88_database, p88_seeded
) -> None:
    service = ValidatedConceptGenerationService(p88_database)
    generated = service.generate_batch(
        batch_request(p88_seeded["brand_one"], count=4, seed=44),
        actor=p88_seeded["producer"],
    )
    assert {row["status"] for row in generated["candidates"]} == {"candidate"}

    for candidate in generated["candidates"]:
        service.review_candidate(
            candidate_id=candidate["id"],
            action=CandidateReviewAction.SHORTLIST,
            rationale="Original, feasible, and aligned with the requested monthly distribution.",
            actor=p88_seeded["reviewer"],
        )

    slate = service.build_slate(
        SlateBuildRequest(
            batch_id=generated["batch"]["id"],
            selected_count=4,
            format_mix={"vertical_short": 2, "carousel": 2},
            pillar_targets={"education": 2, "conservation": 2},
        ),
        actor=p88_seeded["reviewer"],
    )
    assert slate["slate"]["status"] == "draft"
    assert slate["slate"]["gap_report"]["missing_count"] == 0
    assert len(slate["items"]) == 4

    approved = service.approve_slate(
        slate_id=slate["slate"]["id"],
        actor=p88_seeded["reviewer"],
    )
    assert approved["slate"]["status"] == "approved"

    with pytest.raises(psycopg.Error, match="membership and rank are immutable"):
        with p88_database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.concept_slate_items
                   SET rank=99 WHERE slate_id=%s AND candidate_id=%s""",
                (approved["slate"]["id"], approved["items"][0]["candidate_id"]),
            )

    apply_request = SlateApplyRequest(
        plan_id=p88_seeded["plan_one"],
        items=[
            SlateScheduleItem(
                candidate_id=row["candidate_id"],
                scheduled_for=date(2026, 9, index),
            )
            for index, row in enumerate(approved["items"], start=1)
        ],
    )
    applied = service.apply_slate(
        slate_id=approved["slate"]["id"],
        request=apply_request,
        actor=p88_seeded["admin"],
    )
    assert applied["created_count"] == 4

    detail = service.slate_detail(slate_id=approved["slate"]["id"])
    assert detail["slate"]["status"] == "applied"
    assert all(row["candidate_status"] == "accepted" for row in detail["items"])
    assert all(row["applied_content_id"] is not None for row in detail["items"])

    with p88_database.connection() as conn:
        content = conn.execute(
            """SELECT count(*) AS count,
                      count(*) FILTER (WHERE brand_profile_id=%s) AS pinned_count
               FROM football_brief.portfolio_content WHERE plan_id=%s""",
            (p88_seeded["profile_one"], p88_seeded["plan_one"]),
        ).fetchone()
    assert int(content["count"]) == 4
    assert int(content["pinned_count"]) == 4

    with pytest.raises(psycopg.Error, match="Terminal concept candidate status is immutable"):
        with p88_database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.concept_candidates
                   SET status='shortlisted'
                   WHERE id=%s""",
                (detail["items"][0]["candidate_id"],),
            )
