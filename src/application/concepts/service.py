from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

from src.application.concepts.adapters import (
    DeterministicConceptAdapter,
    LocalHttpConceptAdapter,
    build_slots,
    generate_with_fallback,
)
from src.application.concepts.models import (
    CandidateDraft,
    CandidateReviewAction,
    CandidateRevisionRequest,
    ConceptAdapterMode,
    ConceptBatchRequest,
    SlateApplyRequest,
    SlateBuildRequest,
)
from src.application.concepts.scoring import (
    concept_fingerprint,
    find_duplicate,
    score_candidate,
    semantic_key,
    semantic_tokens,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class ConceptServiceError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConceptGenerationService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def generate_batch(self, request: ConceptBatchRequest, *, actor: str) -> dict[str, Any]:
        context = self._load_context(request.brand_id)
        snapshot = {
            "request": request.model_dump(mode="json", exclude={"local_endpoint"}),
            "brand_profile_version": context["brand_profile_version"],
            "reference_source_ids": [row["reference_source_id"] for row in context["reference_patterns"]],
            "performance_package_ids": [row["platform_package_id"] for row in context["performance_signals"]],
            "paid_provider_allowed": False,
        }
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            batch = conn.execute(
                """INSERT INTO football_brief.concept_generation_batches
                   (brand_id, brand_profile_id, month_start, requested_count,
                    requested_format_mix, requested_pillar_targets, seed, adapter_mode,
                    local_model_id, paid_provider_allowed, input_snapshot, created_by)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,false,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.brand_id,
                    context["brand_profile_id"],
                    request.month_start,
                    request.candidate_count,
                    _json(request.format_mix),
                    _json(request.pillar_targets),
                    request.seed,
                    request.adapter_mode.value,
                    request.local_model_id,
                    _json(snapshot),
                    actor,
                ),
            ).fetchone()
        try:
            slots = build_slots(
                format_mix=request.format_mix,
                pillar_targets=request.pillar_targets,
                seed=request.seed,
            )
            fallback = DeterministicConceptAdapter()
            if request.adapter_mode == ConceptAdapterMode.LOCAL_MODEL:
                primary = LocalHttpConceptAdapter(
                    endpoint=request.local_endpoint or "http://127.0.0.1:11434",
                    model_id=request.local_model_id or "",
                    timeout_seconds=request.local_timeout_seconds,
                )
            else:
                primary = fallback
            drafts, adapter_evidence = generate_with_fallback(
                primary=primary,
                fallback=fallback,
                context=context,
                slots=slots,
                seed=request.seed,
            )
            if len(drafts) != request.candidate_count:
                raise ConceptServiceError(
                    "candidate_count_mismatch",
                    details={"requested": request.candidate_count, "generated": len(drafts)},
                )
            self._persist_generated_candidates(
                batch_id=batch["id"],
                drafts=drafts,
                context=context,
                adapter_evidence=adapter_evidence,
            )
        except Exception as exc:
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.concept_generation_batches
                       SET status='failed', completed_at=now(),
                           gap_report=%s::jsonb WHERE id=%s""",
                    (_json({"generation_error": str(exc), "error_type": type(exc).__name__}), batch["id"]),
                )
            if isinstance(exc, ConceptServiceError):
                raise
            raise ConceptServiceError(
                "concept_generation_failed",
                details={"error_type": type(exc).__name__, "message": str(exc)},
            ) from exc
        return self.batch_detail(batch_id=batch["id"])

    def batch_detail(self, *, batch_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            batch = conn.execute(
                """SELECT gb.*, b.slug AS brand_slug, b.display_name AS brand_name,
                          bp.version AS brand_profile_version
                   FROM football_brief.concept_generation_batches gb
                   JOIN football_brief.brands b ON b.id=gb.brand_id
                   JOIN football_brief.brand_profiles bp ON bp.id=gb.brand_profile_id
                   WHERE gb.id=%s""",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ConceptServiceError("concept_batch_not_found")
            candidates = conn.execute(
                """SELECT c.*, duplicate.title AS duplicate_content_title,
                          duplicate_candidate.title AS duplicate_candidate_title
                   FROM football_brief.concept_candidates c
                   LEFT JOIN football_brief.portfolio_content duplicate ON duplicate.id=c.duplicate_content_id
                   LEFT JOIN football_brief.concept_candidates duplicate_candidate ON duplicate_candidate.id=c.duplicate_candidate_id
                   WHERE c.batch_id=%s
                   ORDER BY c.total_score DESC, c.ordinal, c.id""",
                (batch_id,),
            ).fetchall()
            slates = conn.execute(
                """SELECT s.*,
                          COALESCE((SELECT count(*) FROM football_brief.concept_slate_items si WHERE si.slate_id=s.id),0) AS item_count
                   FROM football_brief.concept_slates s
                   WHERE s.batch_id=%s ORDER BY s.version DESC""",
                (batch_id,),
            ).fetchall()
        return {
            "ok": True,
            "batch": dict(batch),
            "candidates": [dict(row) for row in candidates],
            "slates": [dict(row) for row in slates],
        }

    def list_batches(
        self,
        *,
        brand_ids: Iterable[UUID] | None,
        month_start: date | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 200:
            raise ConceptServiceError("invalid_batch_limit")
        conditions = ["true"]
        values: list[Any] = []
        normalized_brands = [UUID(str(value)) for value in brand_ids] if brand_ids is not None else None
        if normalized_brands is not None:
            if not normalized_brands:
                return []
            conditions.append("gb.brand_id=ANY(%s::uuid[])")
            values.append(normalized_brands)
        if month_start:
            conditions.append("gb.month_start=%s")
            values.append(month_start)
        values.append(limit)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT gb.*, b.slug AS brand_slug, b.display_name AS brand_name,
                           bp.version AS brand_profile_version
                    FROM football_brief.concept_generation_batches gb
                    JOIN football_brief.brands b ON b.id=gb.brand_id
                    JOIN football_brief.brand_profiles bp ON bp.id=gb.brand_profile_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY gb.created_at DESC, gb.id DESC LIMIT %s""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def review_candidate(
        self,
        *,
        candidate_id: UUID,
        action: CandidateReviewAction,
        rationale: str,
        actor: str,
    ) -> dict[str, Any]:
        target = {
            CandidateReviewAction.SHORTLIST: "shortlisted",
            CandidateReviewAction.RESTORE: "candidate",
            CandidateReviewAction.REJECT: "rejected",
        }[action]
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                "SELECT * FROM football_brief.concept_candidates WHERE id=%s FOR UPDATE",
                (candidate_id,),
            ).fetchone()
            if not row:
                raise ConceptServiceError("concept_candidate_not_found")
            if row["status"] in {"accepted", "superseded", "duplicate_blocked"}:
                raise ConceptServiceError(
                    "concept_candidate_terminal",
                    details={"status": row["status"]},
                )
            updated = conn.execute(
                """UPDATE football_brief.concept_candidates
                   SET status=%s, review_rationale=%s, reviewed_by=%s, reviewed_at=now()
                   WHERE id=%s RETURNING *""",
                (target, rationale, actor, candidate_id),
            ).fetchone()
            self._refresh_batch_counts(conn, row["batch_id"], status="reviewing")
        return {"ok": True, "candidate": dict(updated)}

    def revise_candidate(
        self,
        *,
        candidate_id: UUID,
        request: CandidateRevisionRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            source = conn.execute(
                """SELECT c.*, gb.brand_id FROM football_brief.concept_candidates c
                   JOIN football_brief.concept_generation_batches gb ON gb.id=c.batch_id
                   WHERE c.id=%s FOR UPDATE OF c""",
                (candidate_id,),
            ).fetchone()
            if not source:
                raise ConceptServiceError("concept_candidate_not_found")
            if source["status"] in {"accepted", "superseded", "duplicate_blocked"}:
                raise ConceptServiceError(
                    "concept_candidate_not_revisable",
                    details={"status": source["status"]},
                )
            context = self._load_context(UUID(str(source["brand_id"])), conn=conn)
            data = {
                "title": source["title"],
                "hook": source["hook"],
                "concept": source["concept"],
                "format": source["format"],
                "pillar": source["pillar"],
                "rationale": source["rationale"],
                "source_requirements": source["source_requirements"],
                "required_research": source["required_research"],
                "factual_risk": source["factual_risk"],
                "production_complexity": source["production_complexity"],
                "estimated_cost_usd": source["estimated_cost_usd"],
                "recommended_route": source["recommended_route"],
                "generation_evidence": {
                    **dict(source["generation_evidence"] or {}),
                    "revision_reason": request.revision_reason,
                    "revised_by": actor,
                    "revised_from_candidate_id": str(candidate_id),
                },
            }
            data.update(request.model_dump(exclude={"revision_reason"}, exclude_none=True, mode="json"))
            draft = CandidateDraft.model_validate(data)
            historical = self._historical_content(conn, UUID(str(source["brand_id"])))
            sibling_rows = conn.execute(
                """SELECT id, title, concept_fingerprint, semantic_tokens
                   FROM football_brief.concept_candidates
                   WHERE batch_id=%s AND id<>%s""",
                (source["batch_id"], candidate_id),
            ).fetchall()
            created = self._insert_candidate(
                conn,
                batch_id=source["batch_id"],
                draft=draft,
                context=context,
                historical=historical,
                sibling_rows=[dict(row) for row in sibling_rows],
                ordinal=self._next_ordinal(conn, source["batch_id"]),
                revised_from_candidate_id=candidate_id,
                adapter_evidence={"adapter": "human_revision", "fallback_used": False},
            )
            conn.execute(
                """UPDATE football_brief.concept_candidates
                   SET status='superseded', review_rationale=%s,
                       reviewed_by=%s, reviewed_at=now()
                   WHERE id=%s""",
                (request.revision_reason, actor, candidate_id),
            )
            self._refresh_batch_counts(conn, source["batch_id"], status="reviewing")
        return {"ok": True, "candidate": dict(created)}

    def build_slate(self, request: SlateBuildRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            batch = conn.execute(
                "SELECT * FROM football_brief.concept_generation_batches WHERE id=%s FOR UPDATE",
                (request.batch_id,),
            ).fetchone()
            if not batch:
                raise ConceptServiceError("concept_batch_not_found")
            rows = conn.execute(
                """SELECT * FROM football_brief.concept_candidates
                   WHERE batch_id=%s AND status='shortlisted'
                   ORDER BY total_score DESC, ordinal, id""",
                (request.batch_id,),
            ).fetchall()
            selected, gap_report = balance_candidates(
                [dict(row) for row in rows],
                selected_count=request.selected_count,
                format_mix=request.format_mix,
                pillar_targets=request.pillar_targets,
            )
            version_row = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM football_brief.concept_slates WHERE batch_id=%s",
                (request.batch_id,),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.concept_slates SET status='superseded'
                   WHERE batch_id=%s AND status='draft'""",
                (request.batch_id,),
            )
            actual_formats = dict(Counter(str(row["format"]) for row in selected))
            actual_pillars = dict(Counter(str(row["pillar"]) for row in selected))
            slate = conn.execute(
                """INSERT INTO football_brief.concept_slates
                   (batch_id, version, requested_count, requested_format_mix,
                    requested_pillar_targets, actual_format_mix, actual_pillar_mix,
                    gap_report, created_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.batch_id,
                    int(version_row["version"]),
                    request.selected_count,
                    _json(request.format_mix),
                    _json(request.pillar_targets),
                    _json(actual_formats),
                    _json(actual_pillars),
                    _json(gap_report),
                    actor,
                ),
            ).fetchone()
            for rank, candidate in enumerate(selected, start=1):
                conn.execute(
                    """INSERT INTO football_brief.concept_slate_items
                       (slate_id, candidate_id, rank) VALUES (%s,%s,%s)""",
                    (slate["id"], candidate["id"], rank),
                )
            conn.execute(
                """UPDATE football_brief.concept_generation_batches
                   SET status='slate_ready', gap_report=%s::jsonb WHERE id=%s""",
                (_json(gap_report), request.batch_id),
            )
        return self.slate_detail(slate_id=slate["id"])

    def slate_detail(self, *, slate_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            slate = conn.execute(
                """SELECT s.*, gb.brand_id, gb.month_start, b.slug AS brand_slug,
                          b.display_name AS brand_name
                   FROM football_brief.concept_slates s
                   JOIN football_brief.concept_generation_batches gb ON gb.id=s.batch_id
                   JOIN football_brief.brands b ON b.id=gb.brand_id
                   WHERE s.id=%s""",
                (slate_id,),
            ).fetchone()
            if not slate:
                raise ConceptServiceError("concept_slate_not_found")
            items = conn.execute(
                """SELECT si.*, c.title, c.hook, c.concept, c.format, c.pillar,
                          c.total_score, c.policy_risk_score, c.feasibility_score,
                          c.estimated_cost_usd, c.recommended_route, c.status AS candidate_status
                   FROM football_brief.concept_slate_items si
                   JOIN football_brief.concept_candidates c ON c.id=si.candidate_id
                   WHERE si.slate_id=%s ORDER BY si.rank""",
                (slate_id,),
            ).fetchall()
        return {"ok": True, "slate": dict(slate), "items": [dict(row) for row in items]}

    def approve_slate(self, *, slate_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            slate = conn.execute(
                "SELECT * FROM football_brief.concept_slates WHERE id=%s FOR UPDATE",
                (slate_id,),
            ).fetchone()
            if not slate:
                raise ConceptServiceError("concept_slate_not_found")
            if slate["status"] == "approved":
                return self.slate_detail(slate_id=slate_id)
            if slate["status"] != "draft":
                raise ConceptServiceError("concept_slate_not_approvable", details={"status": slate["status"]})
            gaps = dict(slate["gap_report"] or {})
            if gaps.get("missing_count", 0) or gaps.get("format_gaps") or gaps.get("pillar_gaps"):
                raise ConceptServiceError("concept_slate_distribution_gap", details=gaps)
            conn.execute(
                """UPDATE football_brief.concept_slates
                   SET status='approved', approved_by=%s, approved_at=now()
                   WHERE id=%s""",
                (actor, slate_id),
            )
        return self.slate_detail(slate_id=slate_id)

    def apply_slate(
        self,
        *,
        slate_id: UUID,
        request: SlateApplyRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            slate = conn.execute(
                """SELECT s.*, gb.brand_id, gb.month_start, gb.id AS batch_id
                   FROM football_brief.concept_slates s
                   JOIN football_brief.concept_generation_batches gb ON gb.id=s.batch_id
                   WHERE s.id=%s FOR UPDATE OF s, gb""",
                (slate_id,),
            ).fetchone()
            if not slate:
                raise ConceptServiceError("concept_slate_not_found")
            if slate["status"] != "approved":
                raise ConceptServiceError("concept_slate_not_approved", details={"status": slate["status"]})
            plan = conn.execute(
                "SELECT * FROM football_brief.monthly_content_plans WHERE id=%s FOR UPDATE",
                (request.plan_id,),
            ).fetchone()
            if not plan:
                raise ConceptServiceError("monthly_plan_not_found")
            if str(plan["brand_id"]) != str(slate["brand_id"]) or plan["month_start"] != slate["month_start"]:
                raise ConceptServiceError("concept_slate_plan_mismatch")
            slate_items = conn.execute(
                """SELECT si.*, c.* FROM football_brief.concept_slate_items si
                   JOIN football_brief.concept_candidates c ON c.id=si.candidate_id
                   WHERE si.slate_id=%s ORDER BY si.rank FOR UPDATE OF si, c""",
                (slate_id,),
            ).fetchall()
            selected_ids = {str(row["candidate_id"]) for row in slate_items}
            requested_ids = {str(item.candidate_id) for item in request.items}
            if selected_ids != requested_ids:
                raise ConceptServiceError(
                    "slate_schedule_candidate_mismatch",
                    details={"selected": sorted(selected_ids), "scheduled": sorted(requested_ids)},
                )
            if len(slate_items) != int(slate["requested_count"]):
                raise ConceptServiceError("concept_slate_incomplete")
            existing_count = conn.execute(
                "SELECT count(*) AS count FROM football_brief.portfolio_content WHERE plan_id=%s",
                (request.plan_id,),
            ).fetchone()
            if int(existing_count["count"]) + len(slate_items) > int(plan["target_count"]):
                raise ConceptServiceError("monthly_plan_target_exceeded")
            item_by_id = {str(item.candidate_id): item for item in request.items}
            historical = self._historical_content(conn, UUID(str(slate["brand_id"])))
            created: list[dict[str, Any]] = []
            for candidate in slate_items:
                schedule = item_by_id[str(candidate["candidate_id"])]
                if schedule.scheduled_for.year != slate["month_start"].year or schedule.scheduled_for.month != slate["month_start"].month:
                    raise ConceptServiceError(
                        "scheduled_date_outside_slate_month",
                        details={"candidate_id": str(candidate["candidate_id"]), "date": schedule.scheduled_for.isoformat()},
                    )
                if candidate["candidate_status"] if "candidate_status" in candidate else candidate["status"] != "shortlisted":
                    pass
                duplicate = find_duplicate(
                    fingerprint=str(candidate["concept_fingerprint"]),
                    tokens=candidate["semantic_tokens"] or (),
                    historical_rows=historical,
                    semantic_threshold=0.72,
                )
                if duplicate:
                    raise ConceptServiceError(
                        "candidate_became_duplicate",
                        details={
                            "candidate_id": str(candidate["candidate_id"]),
                            "duplicate_kind": duplicate.kind,
                            "duplicate_content_id": duplicate.content_id,
                            "similarity": duplicate.similarity,
                        },
                    )
                content = conn.execute(
                    """INSERT INTO football_brief.portfolio_content
                       (plan_id, scheduled_for, title, concept, format,
                        concept_fingerprint, semantic_key, stage, metadata, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'idea',%s::jsonb,%s)
                       RETURNING *""",
                    (
                        request.plan_id,
                        schedule.scheduled_for,
                        candidate["title"],
                        candidate["concept"],
                        candidate["format"],
                        candidate["concept_fingerprint"],
                        candidate["semantic_key"],
                        _json(
                            {
                                "concept_candidate_id": str(candidate["candidate_id"]),
                                "concept_slate_id": str(slate_id),
                                "concept_batch_id": str(slate["batch_id"]),
                                "hook": candidate["hook"],
                                "pillar": candidate["pillar"],
                                "score_evidence": candidate["score_evidence"],
                                "required_research": candidate["required_research"],
                            }
                        ),
                        actor,
                    ),
                ).fetchone()
                conn.execute(
                    """UPDATE football_brief.concept_slate_items
                       SET scheduled_for=%s, applied_content_id=%s
                       WHERE slate_id=%s AND candidate_id=%s""",
                    (schedule.scheduled_for, content["id"], slate_id, candidate["candidate_id"]),
                )
                conn.execute(
                    """UPDATE football_brief.concept_candidates
                       SET status='accepted', accepted_plan_id=%s, accepted_content_id=%s,
                           review_rationale=COALESCE(review_rationale,'Applied from approved slate'),
                           reviewed_by=COALESCE(reviewed_by,%s), reviewed_at=COALESCE(reviewed_at,now())
                       WHERE id=%s""",
                    (request.plan_id, content["id"], actor, candidate["candidate_id"]),
                )
                historical.append(dict(content))
                created.append(dict(content))
            conn.execute("UPDATE football_brief.concept_slates SET status='applied' WHERE id=%s", (slate_id,))
            conn.execute(
                "UPDATE football_brief.concept_generation_batches SET status='applied' WHERE id=%s",
                (slate["batch_id"],),
            )
        return {"ok": True, "slate_id": slate_id, "created_count": len(created), "items": created}

    def _persist_generated_candidates(
        self,
        *,
        batch_id: UUID,
        drafts: list[CandidateDraft],
        context: dict[str, Any],
        adapter_evidence: dict[str, Any],
    ) -> None:
        with self.database.transaction() as conn:
            batch = conn.execute(
                "SELECT * FROM football_brief.concept_generation_batches WHERE id=%s FOR UPDATE",
                (batch_id,),
            ).fetchone()
            if not batch or batch["status"] != "generating":
                raise ConceptServiceError("concept_batch_not_generating")
            historical = self._historical_content(conn, UUID(str(batch["brand_id"])))
            siblings: list[dict[str, Any]] = []
            duplicate_count = 0
            for ordinal, draft in enumerate(drafts, start=1):
                row = self._insert_candidate(
                    conn,
                    batch_id=batch_id,
                    draft=draft,
                    context=context,
                    historical=historical,
                    sibling_rows=siblings,
                    ordinal=ordinal,
                    revised_from_candidate_id=None,
                    adapter_evidence=adapter_evidence,
                )
                siblings.append(dict(row))
                if row["status"] == "duplicate_blocked":
                    duplicate_count += 1
            conn.execute(
                """UPDATE football_brief.concept_generation_batches
                   SET status='ready_for_review', candidate_count=%s,
                       duplicate_count=%s, completed_at=now(),
                       gap_report=%s::jsonb WHERE id=%s""",
                (
                    len(drafts),
                    duplicate_count,
                    _json({"generation": adapter_evidence, "duplicates_blocked": duplicate_count}),
                    batch_id,
                ),
            )

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
        fingerprint = concept_fingerprint(title=draft.title, hook=draft.hook, concept=draft.concept)
        tokens = semantic_tokens(draft.title, draft.hook, draft.concept)
        duplicate = find_duplicate(
            fingerprint=fingerprint,
            tokens=tokens,
            historical_rows=historical,
            candidate_rows=sibling_rows,
            semantic_threshold=0.72,
        )
        score = score_candidate(draft, duplicate=duplicate, context=context)
        status = "duplicate_blocked" if duplicate else "candidate"
        evidence = {
            **dict(draft.generation_evidence),
            **adapter_evidence,
            "brand_profile_id": context["brand_profile_id"],
            "brand_profile_version": context["brand_profile_version"],
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

    def _load_context(self, brand_id: UUID, *, conn=None) -> dict[str, Any]:
        own_connection = conn is None
        manager = self.database.connection() if own_connection else None
        connection = manager.__enter__() if manager else conn
        try:
            profile = connection.execute(
                """SELECT b.id AS brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                          b.niche, b.primary_platform, bp.id AS brand_profile_id,
                          bp.version AS brand_profile_version, bp.default_language,
                          bp.audience, bp.tone, bp.visual_rules, bp.content_restrictions,
                          bp.cadence, bp.platforms, bp.budget
                   FROM football_brief.brands b
                   JOIN football_brief.brand_profiles bp ON bp.brand_id=b.id AND bp.status='active'
                   WHERE b.id=%s AND b.active=true""",
                (brand_id,),
            ).fetchone()
            if not profile:
                raise ConceptServiceError("active_brand_profile_required")
            references = connection.execute(
                """SELECT DISTINCT rs.id AS reference_source_id, rs.platform, rs.canonical_url,
                          COALESCE(rs.source_title, rs.canonical_url) AS pattern
                   FROM football_brief.reference_brand_assignments rba
                   JOIN football_brief.reference_sources rs ON rs.id=rba.reference_source_id
                   WHERE rba.brand_id=%s AND rba.active=true
                     AND EXISTS (
                        SELECT 1 FROM football_brief.reference_approvals ra
                        WHERE ra.reference_source_id=rs.id
                          AND ra.gate='research' AND ra.decision='approved'
                     )
                   ORDER BY rs.id DESC LIMIT 20""",
                (brand_id,),
            ).fetchall()
            performance = connection.execute(
                """SELECT pp.id AS platform_package_id, pp.platform,
                          COALESCE(sum(pm.views),0) AS views,
                          COALESCE(sum(pm.completions),0) AS completions,
                          COALESCE(sum(pm.clicks),0) AS clicks,
                          COALESCE(sum(pm.leads),0) AS leads
                   FROM football_brief.platform_packages pp
                   JOIN football_brief.portfolio_content pc ON pc.id=pp.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.platform_package_metrics pm ON pm.platform_package_id=pp.id
                   WHERE mp.brand_id=%s
                   GROUP BY pp.id, pp.platform
                   ORDER BY views DESC, pp.id DESC LIMIT 20""",
                (brand_id,),
            ).fetchall()
            result = dict(profile)
            result["reference_patterns"] = [dict(row) for row in references]
            result["performance_signals"] = [
                {
                    **dict(row),
                    "signal": f"{row['platform']} package recorded {int(row['views'])} views and {int(row['completions'])} completions",
                }
                for row in performance
            ]
            metadata = result.get("audience") or {}
            result["monetization_goal"] = metadata.get("monetization_goal") if isinstance(metadata, dict) else None
            return result
        finally:
            if manager:
                manager.__exit__(None, None, None)

    @staticmethod
    def _historical_content(conn, brand_id: UUID) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT pc.id, pc.title, pc.concept, pc.script, pc.concept_fingerprint,
                      pc.semantic_key
               FROM football_brief.portfolio_content pc
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE mp.brand_id=%s AND pc.stage<>'archived'
               ORDER BY pc.created_at DESC, pc.id""",
            (brand_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["semantic_tokens"] = semantic_tokens(
                str(item.get("title") or ""),
                str(item.get("concept") or ""),
                _json(item.get("script") or {}),
            )
            result.append(item)
        return result

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not row:
            raise ConceptServiceError("operator_inactive_or_missing")

    @staticmethod
    def _next_ordinal(conn, batch_id: UUID) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(ordinal),0)+1 AS ordinal FROM football_brief.concept_candidates WHERE batch_id=%s",
            (batch_id,),
        ).fetchone()
        return int(row["ordinal"])

    @staticmethod
    def _refresh_batch_counts(conn, batch_id: UUID, *, status: str) -> None:
        counts = conn.execute(
            """SELECT count(*) AS candidate_count,
                      count(*) FILTER (WHERE status='duplicate_blocked') AS duplicate_count,
                      count(*) FILTER (WHERE status='shortlisted') AS shortlisted_count
               FROM football_brief.concept_candidates WHERE batch_id=%s""",
            (batch_id,),
        ).fetchone()
        conn.execute(
            """UPDATE football_brief.concept_generation_batches
               SET status=%s, candidate_count=%s, duplicate_count=%s,
                   shortlisted_count=%s WHERE id=%s""",
            (
                status,
                counts["candidate_count"],
                counts["duplicate_count"],
                counts["shortlisted_count"],
                batch_id,
            ),
        )


def balance_candidates(
    candidates: list[dict[str, Any]],
    *,
    selected_count: int,
    format_mix: dict[str, int],
    pillar_targets: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sum(format_mix.values()) != selected_count or sum(pillar_targets.values()) != selected_count:
        raise ConceptServiceError("slate_distribution_totals_invalid")
    eligible = [
        row
        for row in candidates
        if str(row.get("format")) in format_mix and str(row.get("pillar")) in pillar_targets
    ]
    eligible.sort(key=lambda row: (-float(row["total_score"]), int(row["ordinal"]), str(row["id"])))
    source = "source"
    sink = "sink"
    capacities: dict[tuple[str, str], int] = {}
    costs: dict[tuple[str, str], int] = {}
    adjacency: dict[str, list[str]] = {}

    def add_edge(left: str, right: str, capacity: int, cost: int = 0) -> None:
        capacities[(left, right)] = capacity
        capacities[(right, left)] = 0
        costs[(left, right)] = cost
        costs[(right, left)] = -cost
        adjacency.setdefault(left, []).append(right)
        adjacency.setdefault(right, []).append(left)

    for format_name, count in sorted(format_mix.items()):
        add_edge(source, f"format:{format_name}", count)
    for pillar, count in sorted(pillar_targets.items()):
        add_edge(f"pillar:{pillar}", sink, count)
    candidate_nodes: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(eligible):
        node = f"candidate:{candidate['id']}"
        candidate_nodes[node] = candidate
        add_edge(f"format:{candidate['format']}", node, 1, -int(round(float(candidate["total_score"]) * 1000)) - max(0, 1000 - index))
        add_edge(node, f"pillar:{candidate['pillar']}", 1)

    flow = 0
    while flow < selected_count:
        distance = {node: float("inf") for node in adjacency}
        parent: dict[str, str] = {}
        in_queue = {node: False for node in adjacency}
        distance[source] = 0
        queue = deque([source])
        in_queue[source] = True
        while queue:
            node = queue.popleft()
            in_queue[node] = False
            for neighbor in adjacency.get(node, []):
                if capacities.get((node, neighbor), 0) <= 0:
                    continue
                candidate_distance = distance[node] + costs[(node, neighbor)]
                if candidate_distance < distance[neighbor]:
                    distance[neighbor] = candidate_distance
                    parent[neighbor] = node
                    if not in_queue[neighbor]:
                        queue.append(neighbor)
                        in_queue[neighbor] = True
        if sink not in parent:
            break
        node = sink
        while node != source:
            previous = parent[node]
            capacities[(previous, node)] -= 1
            capacities[(node, previous)] += 1
            node = previous
        flow += 1

    selected = [
        candidate
        for node, candidate in candidate_nodes.items()
        if capacities.get((f"format:{candidate['format']}", node), 0) == 0
    ]
    selected.sort(key=lambda row: (-float(row["total_score"]), int(row["ordinal"]), str(row["id"])))
    actual_formats = Counter(str(row["format"]) for row in selected)
    actual_pillars = Counter(str(row["pillar"]) for row in selected)
    format_gaps = {
        key: target - actual_formats.get(key, 0)
        for key, target in sorted(format_mix.items())
        if actual_formats.get(key, 0) < target
    }
    pillar_gaps = {
        key: target - actual_pillars.get(key, 0)
        for key, target in sorted(pillar_targets.items())
        if actual_pillars.get(key, 0) < target
    }
    gap_report = {
        "requested_count": selected_count,
        "selected_count": len(selected),
        "missing_count": selected_count - len(selected),
        "format_gaps": format_gaps,
        "pillar_gaps": pillar_gaps,
        "eligible_candidate_count": len(eligible),
    }
    return selected, gap_report
