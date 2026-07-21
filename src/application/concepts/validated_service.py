from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.concepts.models import CandidateDraft
from src.application.concepts.safe_service import SafeConceptGenerationService
from src.application.concepts.scoring import (
    concept_fingerprint,
    find_duplicate,
    score_candidate,
    semantic_key,
    semantic_tokens,
)
from src.application.concepts.service import _json


class HistoricalConceptSnapshot(list[dict[str, Any]]):
    """A transaction-start history snapshot.

    Approved candidates in the same slate have already passed the higher same-batch
    duplicate threshold. They must not become historical matches for one another
    merely because application inserts them sequentially in one transaction.
    """

    def append(self, item: dict[str, Any]) -> None:
        return None


class ValidatedConceptGenerationService(SafeConceptGenerationService):
    """Final P88 service with distinct historical and same-batch duplicate policy."""

    def _historical_content(self, conn, brand_id: UUID) -> list[dict[str, Any]]:
        return HistoricalConceptSnapshot(super()._historical_content(conn, brand_id))

    def _insert_candidate(
        self,
        conn,
        *,
        batch_id: UUID,
        draft: CandidateDraft,
        context: dict[str, Any],
        historical: list[dict[str, Any]],
        sibling_rows: list[dict[str, Any]],
        ordinal: int,
        revised_from_candidate_id: UUID | None,
        adapter_evidence: dict[str, Any],
    ):
        fingerprint = concept_fingerprint(
            title=draft.title,
            hook=draft.hook,
            concept=draft.concept,
        )
        tokens = semantic_tokens(draft.title, draft.hook, draft.concept)
        duplicate = find_duplicate(
            fingerprint=fingerprint,
            tokens=tokens,
            historical_rows=historical,
            semantic_threshold=0.72,
        )
        if duplicate is None:
            duplicate = find_duplicate(
                fingerprint=fingerprint,
                tokens=tokens,
                historical_rows=(),
                candidate_rows=sibling_rows,
                semantic_threshold=0.88,
            )
        score = score_candidate(draft, duplicate=duplicate, context=context)
        status = "duplicate_blocked" if duplicate else "candidate"
        evidence = {
            **dict(draft.generation_evidence),
            **adapter_evidence,
            "brand_profile_id": context["brand_profile_id"],
            "brand_profile_version": context["brand_profile_version"],
            "duplicate_policy": {
                "historical_semantic_threshold": 0.72,
                "same_batch_semantic_threshold": 0.88,
                "exact_duplicates_always_blocked": True,
            },
        }
        return conn.execute(
            """INSERT INTO football_brief.concept_candidates
               (batch_id, ordinal, revised_from_candidate_id, status, title, hook,
                concept, format, pillar, rationale, source_requirements,
                required_research, factual_risk, production_complexity,
                estimated_cost_usd, recommended_route, concept_fingerprint,
                semantic_key, semantic_tokens, duplicate_content_id,
                duplicate_candidate_id, duplicate_kind, duplicate_similarity,
                originality_score, engagement_score, monetization_fit_score,
                policy_risk_score, feasibility_score, total_score,
                score_evidence, generation_evidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
               RETURNING *""",
            (
                batch_id,
                ordinal,
                revised_from_candidate_id,
                status,
                draft.title,
                draft.hook,
                draft.concept,
                draft.format,
                draft.pillar,
                draft.rationale,
                _json(draft.source_requirements),
                _json(draft.required_research),
                draft.factual_risk.value,
                draft.production_complexity.value,
                draft.estimated_cost_usd,
                draft.recommended_route.value,
                fingerprint,
                semantic_key(tokens),
                list(tokens),
                UUID(duplicate.content_id) if duplicate and duplicate.content_id else None,
                UUID(duplicate.candidate_id) if duplicate and duplicate.candidate_id else None,
                duplicate.kind if duplicate else None,
                duplicate.similarity if duplicate else None,
                score.originality,
                score.engagement,
                score.monetization_fit,
                score.policy_risk,
                score.feasibility,
                score.total,
                _json(score.evidence),
                _json(evidence),
            ),
        ).fetchone()
