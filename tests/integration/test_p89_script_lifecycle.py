from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from src.application.scripts.adapters import DeterministicScriptAdapter
from src.application.scripts.models import (
    ClaimSourceDraft,
    ClaimSupportType,
    ScriptDecision,
    ScriptGenerateRequest,
    ScriptReviewActionRequest,
    ScriptReviewActionType,
    SourceDraft,
    SourceRightsDeclaration,
    SourceSupportUpdateRequest,
    SourceType,
)
from src.application.scripts.service import ScriptReviewService
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def generation_request(*, target_duration: float = 60, seed: int = 19) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        platform="facebook",
        format="vertical_short",
        language="en-US",
        target_duration_seconds=target_duration,
        words_per_minute=150,
        duration_tolerance_percent=10,
        seed=seed,
    )


def supported_source_request(*, expected_lock: int) -> SourceSupportUpdateRequest:
    source = SourceDraft(
        source_key="source-primary",
        source_type=SourceType.ACADEMIC,
        title="Peer-reviewed evidence for the central biological mechanism",
        publisher="Evidence Journal",
        canonical_url="https://example.org/research/octopus-sensing",
        quality_score=92,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and paraphrased educational explanation",
        evidence_digest="a" * 64,
        notes="No source wording or media is copied into the production output.",
    )
    return SourceSupportUpdateRequest(
        expected_lock_version=expected_lock,
        sources=[source],
        claim_sources=[
            ClaimSourceDraft(
                claim_key="claim-hook",
                source_key=source.source_key,
                support_type=ClaimSupportType.CORROBORATING,
                locator="Abstract and findings",
                support_note="Corroborates the factual opening without supporting absolute wording.",
            ),
            ClaimSourceDraft(
                claim_key="claim-body",
                source_key=source.source_key,
                support_type=ClaimSupportType.DIRECT,
                locator="Methods and findings",
                support_note="Directly supports the central mechanism described in the narration.",
            ),
        ],
        supported_claim_keys=["claim-hook", "claim-body"],
    )


def test_missing_evidence_revision_approval_and_downstream_job_gate(
    p89_database, p89_seeded
) -> None:
    service = ScriptReviewService(p89_database)
    initialized = service.initialize(
        content_id=p89_seeded["content_one"],
        request=generation_request(),
        actor=p89_seeded["producer"],
    )
    document_id = initialized["document"]["id"]
    version_one_id = initialized["document"]["current_version_id"]
    assert initialized["document"]["lock_version"] == 1
    assert initialized["document"]["current_version_status"] == "working"
    assert all(claim["support_status"] == "needs_source" for claim in initialized["claims"])
    assert len(initialized["scenes"]) == len(initialized["sections"])

    with pytest.raises(psycopg.Error, match="approved script_version_id"):
        with p89_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.generation_jobs
                   (portfolio_content_id, content_version, job_type, idempotency_key,
                    input_fingerprint, input_payload, created_by)
                   VALUES (%s,1,'narration','p89-before-script',%s,'{}'::jsonb,%s)""",
                (p89_seeded["content_one"], "1" * 64, p89_seeded["producer"]),
            )

    submitted = service.submit(
        document_id=document_id,
        expected_lock_version=1,
        actor=p89_seeded["producer"],
    )
    assert submitted["document"]["lock_version"] == 2
    assert submitted["document"]["current_version_status"] == "in_review"

    current_claim_id = next(
        claim["id"] for claim in submitted["claims"]
        if str(claim["script_version_id"]) == str(version_one_id)
    )
    with pytest.raises(psycopg.Error, match="Submitted script child evidence is immutable"):
        with p89_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.script_claims SET claim_text='Changed after submission' WHERE id=%s",
                (current_claim_id,),
            )

    with pytest.raises(psycopg.Error, match="Unsupported factual claims"):
        service.decide(
            document_id=document_id,
            expected_lock_version=2,
            decision=ScriptDecision.APPROVED,
            rationale="Attempt approval without evidence",
            reviewer=p89_seeded["reviewer"],
        )

    after_failed_approval = service.detail(document_id=document_id)
    assert after_failed_approval["document"]["lock_version"] == 2
    assert after_failed_approval["decisions"] == []

    section_id = next(
        section["id"] for section in submitted["sections"]
        if str(section["script_version_id"]) == str(version_one_id)
        and section["section_type"] == "narration"
    )
    action_result = service.add_review_action(
        document_id=document_id,
        expected_lock_version=2,
        request=ScriptReviewActionRequest(
            script_version_id=version_one_id,
            script_section_id=section_id,
            action_type=ScriptReviewActionType.SOURCE_REQUEST,
            body="Add a high-quality source and narrow the central wording before approval.",
        ),
        actor=p89_seeded["reviewer"],
    )
    action_id = action_result["action"]["id"]
    assert action_result["document"]["lock_version"] == 3

    changes = service.decide(
        document_id=document_id,
        expected_lock_version=3,
        decision=ScriptDecision.CHANGES_REQUESTED,
        rationale="Evidence and wording changes are required.",
        reviewer=p89_seeded["reviewer"],
    )
    assert changes["document"]["current_version_status"] == "changes_requested"
    assert changes["document"]["lock_version"] == 4

    revised = service.revise(
        document_id=document_id,
        expected_lock_version=4,
        reason="Add source support and address the factual wording request.",
        actor=p89_seeded["producer"],
    )
    version_two_id = revised["document"]["current_version_id"]
    assert str(version_two_id) != str(version_one_id)
    assert revised["document"]["current_version"] == 2
    assert revised["document"]["current_version_status"] == "working"
    assert revised["document"]["lock_version"] == 5
    assert any(
        str(action["id"]) == str(action_id)
        and str(action["script_version_id"]) == str(version_one_id)
        for action in revised["review_actions"]
    )
    assert not any(
        str(action["script_version_id"]) == str(version_two_id)
        for action in revised["review_actions"]
    )

    with pytest.raises(psycopg.Error, match="Stale script versions"):
        with p89_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.script_review_decisions
                   (script_document_id, script_version_id, decision,
                    reviewer_operator_id, rationale, document_lock_version)
                   VALUES (%s,%s,'approved',%s,'Stale approval attempt',5)""",
                (document_id, version_one_id, p89_seeded["reviewer"]),
            )

    supported = service.update_source_support(
        document_id=document_id,
        request=supported_source_request(expected_lock=5),
        actor=p89_seeded["producer"],
    )
    assert supported["document"]["lock_version"] == 6
    current_claims = [
        claim for claim in supported["claims"]
        if str(claim["script_version_id"]) == str(version_two_id)
    ]
    assert {claim["support_status"] for claim in current_claims} == {"supported"}
    assert len([
        link for link in supported["claim_sources"]
        if str(link["script_version_id"]) == str(version_two_id)
    ]) == 2

    resubmitted = service.submit(
        document_id=document_id,
        expected_lock_version=6,
        actor=p89_seeded["producer"],
    )
    assert resubmitted["document"]["lock_version"] == 7

    approved = service.decide(
        document_id=document_id,
        expected_lock_version=7,
        decision=ScriptDecision.APPROVED,
        rationale="Claims, sources, scene plan, duration, and wording are acceptable.",
        reviewer=p89_seeded["reviewer"],
    )
    assert approved["document"]["current_version_status"] == "approved"
    assert approved["document"]["lock_version"] == 8

    with p89_database.transaction() as conn:
        narration = conn.execute(
            """INSERT INTO football_brief.generation_jobs
               (portfolio_content_id, content_version, job_type, idempotency_key,
                input_fingerprint, input_payload, created_by)
               VALUES (%s,1,'narration','p89-approved-narration',%s,%s::jsonb,%s)
               RETURNING id, status""",
            (
                p89_seeded["content_one"],
                "2" * 64,
                f'{{"script_version_id":"{version_two_id}"}}',
                p89_seeded["producer"],
            ),
        ).fetchone()
        preview = conn.execute(
            """INSERT INTO football_brief.generation_jobs
               (portfolio_content_id, content_version, job_type, idempotency_key,
                input_fingerprint, input_payload, created_by)
               VALUES (%s,1,'preview','p89-approved-preview',%s,%s::jsonb,%s)
               RETURNING id, status""",
            (
                p89_seeded["content_one"],
                "3" * 64,
                f'{{"script_version_id":"{version_two_id}"}}',
                p89_seeded["producer"],
            ),
        ).fetchone()
    assert narration["status"] == "queued"
    assert preview["status"] == "queued"

    with pytest.raises(psycopg.Error, match="approved script and scene plan"):
        with p89_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.generation_jobs
                   (portfolio_content_id, content_version, job_type, idempotency_key,
                    input_fingerprint, input_payload, created_by)
                   VALUES (%s,2,'preview','p89-wrong-content-version',%s,%s::jsonb,%s)""",
                (
                    p89_seeded["content_one"],
                    "4" * 64,
                    f'{{"script_version_id":"{version_two_id}"}}',
                    p89_seeded["producer"],
                ),
            )


def test_duration_overflow_blocks_exact_version_approval(p89_database, p89_seeded) -> None:
    service = ScriptReviewService(p89_database)
    initialized = service.initialize(
        content_id=p89_seeded["content_two"],
        request=generation_request(target_duration=60, seed=77),
        actor=p89_seeded["outsider"],
    )
    document_id = initialized["document"]["id"]
    context = service._context(p89_seeded["content_two"])
    long_draft = DeterministicScriptAdapter().generate(
        context=context,
        configuration=generation_request(target_duration=60, seed=77),
    ).model_copy(update={"target_duration_seconds": 5, "duration_tolerance_percent": 0})
    replaced = service.replace_working_draft(
        document_id=document_id,
        expected_lock_version=1,
        draft=long_draft,
        actor=p89_seeded["outsider"],
    )
    assert replaced["document"]["lock_version"] == 2
    supported = service.update_source_support(
        document_id=document_id,
        request=supported_source_request(expected_lock=2),
        actor=p89_seeded["outsider"],
    )
    assert supported["document"]["lock_version"] == 3
    service.submit(
        document_id=document_id,
        expected_lock_version=3,
        actor=p89_seeded["outsider"],
    )
    with pytest.raises(psycopg.Error, match="duration exceeds"):
        service.decide(
            document_id=document_id,
            expected_lock_version=4,
            decision=ScriptDecision.APPROVED,
            rationale="Attempt approval despite duration overflow.",
            reviewer=p89_seeded["admin"],
        )
