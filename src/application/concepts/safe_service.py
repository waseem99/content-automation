from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any
from uuid import UUID

from src.application.concepts.models import SlateApplyRequest
from src.application.concepts.scoring import find_duplicate
from src.application.concepts.service import ConceptGenerationService, ConceptServiceError, _json


class SafeConceptGenerationService(ConceptGenerationService):
    """Schema-validated P88 service facade.

    The generation and candidate-review behavior remains in ConceptGenerationService.
    This facade overrides the database-sensitive context and slate operations so they
    use only canonical repository tables and fail closed during approval/application.
    """

    def _load_context(self, brand_id: UUID, *, conn=None) -> dict[str, Any]:
        if conn is not None:
            return self._load_context_from_connection(conn, brand_id)
        with self.database.connection() as connection:
            return self._load_context_from_connection(connection, brand_id)

    @staticmethod
    def _load_context_from_connection(connection, brand_id: UUID) -> dict[str, Any]:
        profile = connection.execute(
            """SELECT b.id AS brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                      b.niche, b.primary_platform, bp.id AS brand_profile_id,
                      bp.version AS brand_profile_version, bp.default_language,
                      bp.audience, bp.tone, bp.visual_rules, bp.content_restrictions,
                      bp.cadence, bp.platforms, bp.budget
               FROM football_brief.brands b
               JOIN football_brief.brand_profiles bp
                 ON bp.brand_id=b.id AND bp.status='active'
               WHERE b.id=%s AND b.active=true""",
            (brand_id,),
        ).fetchone()
        if not profile:
            raise ConceptServiceError("active_brand_profile_required")

        references = connection.execute(
            """SELECT DISTINCT rs.id AS reference_source_id, rs.platform,
                      rs.canonical_url, rs.title AS pattern
               FROM football_brief.reference_brand_assignments rba
               JOIN football_brief.reference_sources rs
                 ON rs.id=rba.reference_source_id
               WHERE rba.brand_id=%s
                 AND rba.active=true
                 AND rs.status='ready_for_review'
                 AND NOT EXISTS (
                     SELECT 1
                     FROM (VALUES ('rights'), ('originality'), ('editorial')) required(gate)
                     WHERE COALESCE((
                         SELECT rag.decision
                         FROM football_brief.reference_approval_gates rag
                         WHERE rag.reference_source_id=rs.id
                           AND rag.gate=required.gate
                         ORDER BY rag.version DESC, rag.created_at DESC, rag.id DESC
                         LIMIT 1
                     ), 'pending') <> 'approved'
                 )
               ORDER BY rs.id DESC
               LIMIT 20""",
            (brand_id,),
        ).fetchall()

        performance = connection.execute(
            """SELECT pp.id AS platform_package_id, pp.platform,
                      COALESCE(sum(po.views),0) AS views,
                      COALESCE(avg(po.average_view_percentage),0) AS average_view_percentage,
                      COALESCE(avg(po.three_second_view_rate),0) AS three_second_view_rate,
                      COALESCE(sum(po.engagements),0) AS engagements,
                      COALESCE(sum(po.shares),0) AS shares,
                      COALESCE(sum(po.followers_gained),0) AS followers_gained,
                      COALESCE(sum(po.revenue_usd),0) AS revenue_usd
               FROM football_brief.platform_packages pp
               JOIN football_brief.portfolio_content pc ON pc.id=pp.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               JOIN football_brief.performance_observations po
                 ON po.platform_package_id=pp.id
               WHERE mp.brand_id=%s
               GROUP BY pp.id, pp.platform
               ORDER BY views DESC, engagements DESC, pp.id DESC
               LIMIT 20""",
            (brand_id,),
        ).fetchall()

        result = dict(profile)
        result["reference_patterns"] = [dict(row) for row in references]
        result["performance_signals"] = [
            {
                **dict(row),
                "signal": (
                    f"{row['platform']} package recorded {int(row['views'])} views, "
                    f"{int(row['engagements'])} engagements, and "
                    f"{float(row['average_view_percentage']):.1f}% average viewing"
                ),
            }
            for row in performance
        ]
        audience = result.get("audience") or {}
        result["monetization_goal"] = (
            audience.get("monetization_goal") if isinstance(audience, dict) else None
        )
        return result

    def approve_slate(self, *, slate_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            slate = conn.execute(
                """SELECT s.*, gb.status AS batch_status
                   FROM football_brief.concept_slates s
                   JOIN football_brief.concept_generation_batches gb ON gb.id=s.batch_id
                   WHERE s.id=%s
                   FOR UPDATE OF s, gb""",
                (slate_id,),
            ).fetchone()
            if not slate:
                raise ConceptServiceError("concept_slate_not_found")
            if slate["status"] == "approved":
                pass
            elif slate["status"] != "draft":
                raise ConceptServiceError(
                    "concept_slate_not_approvable", details={"status": slate["status"]}
                )
            else:
                if slate["batch_status"] != "slate_ready":
                    raise ConceptServiceError(
                        "concept_batch_not_slate_ready",
                        details={"status": slate["batch_status"]},
                    )
                items = conn.execute(
                    """SELECT c.id, c.status, c.format, c.pillar
                       FROM football_brief.concept_slate_items si
                       JOIN football_brief.concept_candidates c ON c.id=si.candidate_id
                       WHERE si.slate_id=%s
                       ORDER BY si.rank
                       FOR UPDATE OF c""",
                    (slate_id,),
                ).fetchall()
                requested_count = int(slate["requested_count"])
                if len(items) != requested_count:
                    raise ConceptServiceError(
                        "concept_slate_incomplete",
                        details={"requested": requested_count, "actual": len(items)},
                    )
                invalid = [str(row["id"]) for row in items if row["status"] != "shortlisted"]
                if invalid:
                    raise ConceptServiceError(
                        "concept_slate_candidate_status_invalid",
                        details={"candidate_ids": invalid},
                    )
                actual_formats = dict(Counter(str(row["format"]) for row in items))
                actual_pillars = dict(Counter(str(row["pillar"]) for row in items))
                requested_formats = {
                    str(key): int(value)
                    for key, value in dict(slate["requested_format_mix"] or {}).items()
                }
                requested_pillars = {
                    str(key): int(value)
                    for key, value in dict(slate["requested_pillar_targets"] or {}).items()
                }
                if actual_formats != requested_formats or actual_pillars != requested_pillars:
                    raise ConceptServiceError(
                        "concept_slate_distribution_gap",
                        details={
                            "requested_format_mix": requested_formats,
                            "actual_format_mix": actual_formats,
                            "requested_pillar_targets": requested_pillars,
                            "actual_pillar_mix": actual_pillars,
                        },
                    )
                gaps = dict(slate["gap_report"] or {})
                if gaps.get("missing_count", 0) or gaps.get("format_gaps") or gaps.get("pillar_gaps"):
                    raise ConceptServiceError("concept_slate_distribution_gap", details=gaps)
                updated = conn.execute(
                    """UPDATE football_brief.concept_slates
                       SET status='approved', approved_by=%s, approved_at=now()
                       WHERE id=%s AND status='draft'
                       RETURNING id""",
                    (actor, slate_id),
                ).fetchone()
                if not updated:
                    raise ConceptServiceError("concept_slate_approval_conflict")
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
                """SELECT s.*, gb.brand_id, gb.brand_profile_id, gb.month_start,
                          gb.id AS generation_batch_id, gb.status AS batch_status
                   FROM football_brief.concept_slates s
                   JOIN football_brief.concept_generation_batches gb ON gb.id=s.batch_id
                   WHERE s.id=%s
                   FOR UPDATE OF s, gb""",
                (slate_id,),
            ).fetchone()
            if not slate:
                raise ConceptServiceError("concept_slate_not_found")
            if slate["status"] != "approved":
                raise ConceptServiceError(
                    "concept_slate_not_approved", details={"status": slate["status"]}
                )
            if slate["batch_status"] != "slate_ready":
                raise ConceptServiceError(
                    "concept_batch_not_slate_ready", details={"status": slate["batch_status"]}
                )

            plan = conn.execute(
                """SELECT * FROM football_brief.monthly_content_plans
                   WHERE id=%s FOR UPDATE""",
                (request.plan_id,),
            ).fetchone()
            if not plan:
                raise ConceptServiceError("monthly_plan_not_found")
            if plan["status"] != "draft":
                raise ConceptServiceError(
                    "monthly_plan_not_draft", details={"status": plan["status"]}
                )
            if (
                str(plan["brand_id"]) != str(slate["brand_id"])
                or plan["month_start"] != slate["month_start"]
            ):
                raise ConceptServiceError("concept_slate_plan_mismatch")

            slate_items = conn.execute(
                """SELECT si.rank, si.candidate_id, si.scheduled_for,
                          si.applied_content_id, c.status AS candidate_status,
                          c.title, c.hook, c.concept, c.format, c.pillar,
                          c.concept_fingerprint, c.semantic_key, c.semantic_tokens,
                          c.score_evidence, c.required_research
                   FROM football_brief.concept_slate_items si
                   JOIN football_brief.concept_candidates c ON c.id=si.candidate_id
                   WHERE si.slate_id=%s
                   ORDER BY si.rank
                   FOR UPDATE OF si, c""",
                (slate_id,),
            ).fetchall()
            if len(slate_items) != int(slate["requested_count"]):
                raise ConceptServiceError("concept_slate_incomplete")
            invalid_statuses = [
                str(row["candidate_id"])
                for row in slate_items
                if row["candidate_status"] != "shortlisted"
            ]
            if invalid_statuses:
                raise ConceptServiceError(
                    "concept_slate_candidate_status_invalid",
                    details={"candidate_ids": invalid_statuses},
                )

            selected_ids = {str(row["candidate_id"]) for row in slate_items}
            requested_ids = {str(item.candidate_id) for item in request.items}
            if selected_ids != requested_ids or len(request.items) != len(slate_items):
                raise ConceptServiceError(
                    "slate_schedule_candidate_mismatch",
                    details={"selected": sorted(selected_ids), "scheduled": sorted(requested_ids)},
                )

            existing_count = conn.execute(
                "SELECT count(*) AS count FROM football_brief.portfolio_content WHERE plan_id=%s",
                (request.plan_id,),
            ).fetchone()
            if int(existing_count["count"]) + len(slate_items) > int(plan["target_count"]):
                raise ConceptServiceError("monthly_plan_target_exceeded")

            schedule_by_id = {str(item.candidate_id): item for item in request.items}
            month_start: date = slate["month_start"]
            historical = self._historical_content(conn, UUID(str(slate["brand_id"])))
            created: list[dict[str, Any]] = []

            for candidate in slate_items:
                candidate_id = str(candidate["candidate_id"])
                schedule = schedule_by_id[candidate_id]
                if (
                    schedule.scheduled_for.year != month_start.year
                    or schedule.scheduled_for.month != month_start.month
                ):
                    raise ConceptServiceError(
                        "scheduled_date_outside_slate_month",
                        details={
                            "candidate_id": candidate_id,
                            "date": schedule.scheduled_for.isoformat(),
                        },
                    )
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
                            "candidate_id": candidate_id,
                            "duplicate_kind": duplicate.kind,
                            "duplicate_content_id": duplicate.content_id,
                            "similarity": duplicate.similarity,
                        },
                    )

                content = conn.execute(
                    """INSERT INTO football_brief.portfolio_content
                       (plan_id, scheduled_for, title, concept, format,
                        concept_fingerprint, semantic_key, stage, metadata,
                        brand_profile_id)
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
                                "concept_candidate_id": candidate_id,
                                "concept_slate_id": str(slate_id),
                                "concept_batch_id": str(slate["generation_batch_id"]),
                                "created_by": actor,
                                "hook": candidate["hook"],
                                "pillar": candidate["pillar"],
                                "score_evidence": candidate["score_evidence"],
                                "required_research": candidate["required_research"],
                            }
                        ),
                        slate["brand_profile_id"],
                    ),
                ).fetchone()

                accepted = conn.execute(
                    """UPDATE football_brief.concept_candidates
                       SET status='accepted', accepted_plan_id=%s, accepted_content_id=%s,
                           review_rationale=COALESCE(review_rationale,'Applied from approved slate'),
                           reviewed_by=COALESCE(reviewed_by,%s),
                           reviewed_at=COALESCE(reviewed_at,now())
                       WHERE id=%s AND status='shortlisted'
                       RETURNING id""",
                    (request.plan_id, content["id"], actor, candidate["candidate_id"]),
                ).fetchone()
                if not accepted:
                    raise ConceptServiceError(
                        "concept_candidate_application_conflict",
                        details={"candidate_id": candidate_id},
                    )

                applied_item = conn.execute(
                    """UPDATE football_brief.concept_slate_items
                       SET scheduled_for=%s, applied_content_id=%s
                       WHERE slate_id=%s AND candidate_id=%s
                         AND scheduled_for IS NULL AND applied_content_id IS NULL
                       RETURNING candidate_id""",
                    (
                        schedule.scheduled_for,
                        content["id"],
                        slate_id,
                        candidate["candidate_id"],
                    ),
                ).fetchone()
                if not applied_item:
                    raise ConceptServiceError(
                        "concept_slate_item_application_conflict",
                        details={"candidate_id": candidate_id},
                    )

                historical.append(
                    {
                        **dict(content),
                        "semantic_tokens": tuple(candidate["semantic_tokens"] or ()),
                    }
                )
                created.append(dict(content))

            applied_slate = conn.execute(
                """UPDATE football_brief.concept_slates
                   SET status='applied'
                   WHERE id=%s AND status='approved'
                   RETURNING id""",
                (slate_id,),
            ).fetchone()
            if not applied_slate:
                raise ConceptServiceError("concept_slate_application_conflict")
            applied_batch = conn.execute(
                """UPDATE football_brief.concept_generation_batches
                   SET status='applied'
                   WHERE id=%s AND status='slate_ready'
                   RETURNING id""",
                (slate["generation_batch_id"],),
            ).fetchone()
            if not applied_batch:
                raise ConceptServiceError("concept_batch_application_conflict")

        return {
            "ok": True,
            "slate_id": slate_id,
            "created_count": len(created),
            "items": created,
        }
