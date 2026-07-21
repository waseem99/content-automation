from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.routing.models import (
    BudgetPolicyRequest,
    ReserveAndEnqueueRequest,
    RoutingPlanRequest,
    ShotRoute,
    ShotRoutingInput,
    SpendDecisionRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class RoutingSpendError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


class RoutingSpendService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.jobs = GenerationJobService(database)

    def create_policy(self, *, request: BudgetPolicyRequest, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            version = 1
            if request.parent_policy_id:
                parent = conn.execute(
                    "SELECT * FROM football_brief.production_budget_policies WHERE id=%s FOR UPDATE",
                    (request.parent_policy_id,),
                ).fetchone()
                if not parent:
                    raise RoutingSpendError("budget_policy_parent_not_found")
                if parent["brand_id"] != request.brand_id or parent["month_start"] != request.month_start:
                    raise RoutingSpendError("budget_policy_parent_identity_mismatch")
                version = int(parent["version"]) + 1
            else:
                existing = conn.execute(
                    """SELECT 1 FROM football_brief.production_budget_policies
                       WHERE brand_id=%s AND month_start=%s""",
                    (request.brand_id, request.month_start),
                ).fetchone()
                if existing:
                    raise RoutingSpendError("budget_policy_parent_required")
            row = conn.execute(
                """INSERT INTO football_brief.production_budget_policies
                   (brand_id,month_start,version,parent_policy_id,status,currency,
                    monthly_soft_limit,monthly_hard_limit,default_content_limit,
                    approval_threshold,require_approval_for_managed,created_by)
                   VALUES (%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.brand_id,
                    request.month_start,
                    version,
                    request.parent_policy_id,
                    request.currency,
                    request.monthly_soft_limit,
                    request.monthly_hard_limit,
                    request.default_content_limit,
                    request.approval_threshold,
                    request.require_approval_for_managed,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "policy": dict(row)}

    def activate_policy(self, *, policy_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            policy = conn.execute(
                "SELECT * FROM football_brief.production_budget_policies WHERE id=%s FOR UPDATE",
                (policy_id,),
            ).fetchone()
            if not policy:
                raise RoutingSpendError("budget_policy_not_found")
            if policy["status"] != "draft":
                raise RoutingSpendError("budget_policy_not_draft")
            active = conn.execute(
                """SELECT id FROM football_brief.production_budget_policies
                   WHERE brand_id=%s AND month_start=%s AND status='active' FOR UPDATE""",
                (policy["brand_id"], policy["month_start"]),
            ).fetchone()
            if active:
                conn.execute(
                    """UPDATE football_brief.production_budget_policies
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, active["id"]),
                )
            activated = conn.execute(
                """UPDATE football_brief.production_budget_policies
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, policy_id),
            ).fetchone()
        return {"ok": True, "policy": dict(activated)}

    def list_policies(self, *, brand_id: UUID | None = None, month_start=None) -> list[dict[str, Any]]:
        conditions = ["true"]
        values: list[Any] = []
        if brand_id:
            conditions.append("brand_id=%s")
            values.append(brand_id)
        if month_start:
            conditions.append("month_start=%s")
            values.append(month_start)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT * FROM football_brief.production_budget_policies
                    WHERE {' AND '.join(conditions)} ORDER BY month_start DESC,version DESC""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_plan(
        self,
        *,
        content_id: UUID,
        request: RoutingPlanRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            context = conn.execute(
                """SELECT pc.id AS content_id,pc.version AS content_version,mp.brand_id,mp.month_start,
                          vp.id AS visual_project_id,vp.status AS visual_status
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.visual_projects vp ON vp.portfolio_content_id=pc.id
                   WHERE pc.id=%s AND vp.status='approved'
                   ORDER BY vp.decided_at DESC NULLS LAST,vp.created_at DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
            if not context:
                raise RoutingSpendError("approved_visual_project_required")
            policy = conn.execute(
                """SELECT * FROM football_brief.production_budget_policies
                   WHERE id=%s AND status='active' FOR UPDATE""",
                (request.budget_policy_id,),
            ).fetchone()
            if not policy or policy["brand_id"] != context["brand_id"] or policy["month_start"] != context["month_start"]:
                raise RoutingSpendError("active_matching_budget_policy_required")

            shots = conn.execute(
                """SELECT vs.id,vs.sequence,vs.selected_candidate_id,vc.asset_id
                   FROM football_brief.visual_shots vs
                   JOIN football_brief.visual_candidates vc ON vc.id=vs.selected_candidate_id
                   WHERE vs.visual_project_id=%s AND vs.status='approved'
                   ORDER BY vs.sequence""",
                (context["visual_project_id"],),
            ).fetchall()
            if not shots:
                raise RoutingSpendError("approved_visual_shots_required")
            input_map = {item.visual_shot_id: item for item in request.shots}
            expected_ids = {row["id"] for row in shots}
            if set(input_map) != expected_ids:
                raise RoutingSpendError(
                    "routing_inputs_must_cover_every_shot",
                    details={
                        "missing": [str(item) for item in sorted(expected_ids - set(input_map), key=str)],
                        "extra": [str(item) for item in sorted(set(input_map) - expected_ids, key=str)],
                    },
                )

            version = 1
            parent = None
            if request.parent_plan_id:
                parent = conn.execute(
                    "SELECT * FROM football_brief.shot_routing_plans WHERE id=%s FOR UPDATE",
                    (request.parent_plan_id,),
                ).fetchone()
                if not parent:
                    raise RoutingSpendError("routing_parent_not_found")
                if parent["portfolio_content_id"] != content_id or int(parent["content_version"]) != int(context["content_version"]):
                    raise RoutingSpendError("routing_parent_identity_mismatch")
                version = int(parent["version"]) + 1
                if parent["status"] == "approved":
                    conn.execute(
                        """UPDATE football_brief.shot_routing_plans
                           SET status='superseded',lock_version=lock_version+1
                           WHERE id=%s""",
                        (parent["id"],),
                    )

            plan = conn.execute(
                """INSERT INTO football_brief.shot_routing_plans
                   (portfolio_content_id,content_version,visual_project_id,budget_policy_id,
                    version,parent_plan_id,status,recommendation_snapshot,lock_version,
                    created_by,last_edited_by)
                   VALUES (%s,%s,%s,%s,%s,%s,'draft',%s::jsonb,1,%s,%s) RETURNING *""",
                (
                    content_id,
                    context["content_version"],
                    context["visual_project_id"],
                    policy["id"],
                    version,
                    request.parent_plan_id,
                    _json({
                        "router_version": "p94-router-v1",
                        "context": request.recommendation_context,
                        "policy_id": str(policy["id"]),
                    }),
                    actor,
                    actor,
                ),
            ).fetchone()

            created_items = []
            for shot in shots:
                routing_input = input_map[shot["id"]]
                preflight = None
                if routing_input.renderer_preflight_id:
                    preflight = conn.execute(
                        """SELECT rp.*,rce.provider_key,rce.model_key,rce.health_status,
                                  rce.quality_rating,rce.capabilities
                           FROM football_brief.renderer_preflight_records rp
                           LEFT JOIN football_brief.renderer_catalogue_entries rce
                             ON rce.id=rp.renderer_catalogue_entry_id
                           WHERE rp.id=%s""",
                        (routing_input.renderer_preflight_id,),
                    ).fetchone()
                route, rationale, alternatives = self._recommend_route(routing_input, preflight)
                estimate = _decimal(preflight["estimated_cost"]) if route == ShotRoute.MANAGED_RENDER else Decimal("0")
                row = conn.execute(
                    """INSERT INTO football_brief.shot_routing_items
                       (routing_plan_id,visual_shot_id,selected_candidate_id,route,
                        renderer_preflight_id,hero_importance,realism_requirement,
                        motion_complexity,continuity_requirement,factual_control_requirement,
                        local_preview_quality,engagement_contribution,estimated_cost,rationale,alternatives)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                       RETURNING *""",
                    (
                        plan["id"],
                        shot["id"],
                        shot["selected_candidate_id"],
                        route.value,
                        preflight["id"] if route == ShotRoute.MANAGED_RENDER and preflight else None,
                        routing_input.hero_importance,
                        routing_input.realism_requirement,
                        routing_input.motion_complexity,
                        routing_input.continuity_requirement,
                        routing_input.factual_control_requirement,
                        routing_input.local_preview_quality,
                        routing_input.engagement_contribution,
                        estimate,
                        rationale,
                        _json(alternatives),
                    ),
                ).fetchone()
                created_items.append(dict(row))
                if routing_input.forced_route:
                    conn.execute(
                        """INSERT INTO football_brief.production_spend_events
                           (routing_plan_id,event,actor,details)
                           VALUES (%s,'route_overridden',%s,%s::jsonb)""",
                        (
                            plan["id"],
                            actor,
                            _json({
                                "routing_item_id": str(row["id"]),
                                "visual_shot_id": str(shot["id"]),
                                "forced_route": route.value,
                                "rationale": routing_input.override_rationale,
                            }),
                        ),
                    )
            conn.execute(
                """INSERT INTO football_brief.production_spend_events
                   (routing_plan_id,event,actor,details)
                   VALUES (%s,'plan_created',%s,%s::jsonb)""",
                (plan["id"], actor, _json({"version": version, "shot_count": len(created_items)})),
            )
        return self.detail(plan_id=plan["id"])

    def submit(self, *, plan_id: UUID, expected_lock_version: int, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            updated = conn.execute(
                """UPDATE football_brief.shot_routing_plans
                   SET status='in_review',submitted_at=now(),last_edited_by=%s,
                       lock_version=lock_version+1
                   WHERE id=%s AND status='draft' AND lock_version=%s RETURNING *""",
                (actor, plan_id, expected_lock_version),
            ).fetchone()
            if not updated:
                raise RoutingSpendError("routing_plan_conflict_or_not_draft")
            conn.execute(
                """INSERT INTO football_brief.production_spend_events
                   (routing_plan_id,event,actor,details)
                   VALUES (%s,'plan_submitted',%s,%s::jsonb)""",
                (plan_id, actor, _json({"lock_version": updated["lock_version"]})),
            )
        return self.detail(plan_id=plan_id)

    def decide(
        self,
        *,
        plan_id: UUID,
        request: SpendDecisionRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            decision = conn.execute(
                """INSERT INTO football_brief.production_spend_decisions
                   (routing_plan_id,decision,approved_ceiling,reviewer_operator_id,
                    rationale,plan_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    plan_id,
                    request.decision.value,
                    request.approved_ceiling,
                    reviewer,
                    request.rationale,
                    request.expected_lock_version,
                ),
            ).fetchone()
        return self.detail(plan_id=plan_id)

    def reserve_and_enqueue(
        self,
        *,
        plan_id: UUID,
        request: ReserveAndEnqueueRequest,
        actor: str,
    ) -> dict[str, Any]:
        reservation = None
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """SELECT sri.*,srp.portfolio_content_id,srp.content_version,srp.status AS plan_status,
                          rp.request_payload,rp.request_fingerprint,rp.renderer_catalogue_entry_id,
                          rce.provider_key,rce.model_key,rce.adapter_kind,rce.status AS renderer_status,
                          rce.health_status
                   FROM football_brief.shot_routing_items sri
                   JOIN football_brief.shot_routing_plans srp ON srp.id=sri.routing_plan_id
                   JOIN football_brief.renderer_preflight_records rp ON rp.id=sri.renderer_preflight_id
                   JOIN football_brief.renderer_catalogue_entries rce ON rce.id=rp.renderer_catalogue_entry_id
                   WHERE sri.id=%s AND srp.id=%s FOR UPDATE OF sri,srp""",
                (request.routing_item_id, plan_id),
            ).fetchone()
            if not row:
                raise RoutingSpendError("managed_routing_item_not_found")
            if row["route"] != ShotRoute.MANAGED_RENDER.value or row["plan_status"] != "approved":
                raise RoutingSpendError("approved_managed_routing_required")
            if row["renderer_status"] != "active" or row["health_status"] not in {"healthy", "degraded"}:
                raise RoutingSpendError("renderer_not_available")
            reservation_key = f"routing:{plan_id}:{request.routing_item_id}:{row['renderer_preflight_id']}"
            existing = conn.execute(
                "SELECT * FROM football_brief.production_spend_reservations WHERE reservation_key=%s FOR UPDATE",
                (reservation_key,),
            ).fetchone()
            if existing:
                reservation = dict(existing)
                if existing["status"] != "reserved":
                    raise RoutingSpendError("spend_reservation_not_available")
            else:
                inserted = conn.execute(
                    """INSERT INTO football_brief.production_spend_reservations
                       (routing_plan_id,routing_item_id,renderer_preflight_id,portfolio_content_id,
                        content_version,reserved_amount,status,reservation_key,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,'reserved',%s,%s) RETURNING *""",
                    (
                        plan_id,
                        row["id"],
                        row["renderer_preflight_id"],
                        row["portfolio_content_id"],
                        row["content_version"],
                        row["estimated_cost"],
                        reservation_key,
                        actor,
                    ),
                ).fetchone()
                reservation = dict(inserted)
                conn.execute(
                    """INSERT INTO football_brief.production_spend_events
                       (routing_plan_id,reservation_id,event,actor,details)
                       VALUES (%s,%s,'reservation_created',%s,%s::jsonb)""",
                    (
                        plan_id,
                        reservation["id"],
                        actor,
                        _json({
                            "routing_item_id": str(row["id"]),
                            "reserved_amount": str(row["estimated_cost"]),
                            "soft_limit_exceeded": reservation["soft_limit_exceeded"],
                        }),
                    ),
                )

        if reservation["generation_job_id"]:
            return {
                "ok": True,
                "reservation": reservation,
                "job": self.jobs.detail(job_id=reservation["generation_job_id"])["job"],
                "reused": True,
            }

        input_payload = {
            "spend_reservation_id": str(reservation["id"]),
            "routing_plan_id": str(plan_id),
            "routing_item_id": str(row["id"]),
            "renderer_preflight_id": str(row["renderer_preflight_id"]),
            "renderer_catalogue_entry_id": str(row["renderer_catalogue_entry_id"]),
            "request_fingerprint": row["request_fingerprint"],
            "request": dict(row["request_payload"]),
            "selected_candidate_id": str(row["selected_candidate_id"]),
        }
        try:
            job = self.jobs.enqueue(
                GenerationJobEnqueue(
                    portfolio_content_id=row["portfolio_content_id"],
                    content_version=int(row["content_version"]),
                    production_workflow_id=request.production_workflow_id,
                    production_workflow_version_id=request.production_workflow_version_id,
                    job_type=GenerationJobType.PREMIUM_CLIP,
                    provider=row["provider_key"],
                    model_id=row["model_key"],
                    preferred_worker_id=request.preferred_worker_id,
                    priority=request.priority,
                    idempotency_key=f"managed:{reservation['id']}",
                    input_payload=input_payload,
                    timeout_seconds=request.timeout_seconds,
                    max_attempts=request.max_attempts,
                    estimated_cost_usd=_decimal(row["estimated_cost"]),
                    reserved_cost_usd=_decimal(row["estimated_cost"]),
                ),
                actor=actor,
            )
            with self.database.transaction() as conn:
                bound = conn.execute(
                    """UPDATE football_brief.production_spend_reservations
                       SET generation_job_id=%s,bound_at=now()
                       WHERE id=%s AND status='reserved' AND generation_job_id IS NULL
                       RETURNING *""",
                    (job["id"], reservation["id"]),
                ).fetchone()
                if not bound:
                    raise RoutingSpendError("spend_reservation_binding_conflict")
                conn.execute(
                    """INSERT INTO football_brief.renderer_job_bindings
                       (generation_job_id,renderer_preflight_id,renderer_catalogue_entry_id,
                        request_fingerprint,created_by)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (generation_job_id) DO NOTHING""",
                    (
                        job["id"],
                        row["renderer_preflight_id"],
                        row["renderer_catalogue_entry_id"],
                        row["request_fingerprint"],
                        actor,
                    ),
                )
                conn.execute(
                    """INSERT INTO football_brief.production_spend_events
                       (routing_plan_id,reservation_id,event,actor,details)
                       VALUES (%s,%s,'reservation_bound',%s,%s::jsonb)""",
                    (plan_id, reservation["id"], actor, _json({"generation_job_id": str(job["id"])})),
                )
            return {"ok": True, "reservation": dict(bound), "job": job, "reused": bool(job.get("reused"))}
        except Exception:
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.production_spend_reservations
                       SET status='released',released_at=now()
                       WHERE id=%s AND status='reserved' AND generation_job_id IS NULL""",
                    (reservation["id"],),
                )
                conn.execute(
                    """INSERT INTO football_brief.production_spend_events
                       (routing_plan_id,reservation_id,event,actor,details)
                       VALUES (%s,%s,'reservation_released',%s,%s::jsonb)""",
                    (plan_id, reservation["id"], actor, _json({"reason": "enqueue_failed"})),
                )
            raise

    def detail(self, *, plan_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            plan = conn.execute(
                """SELECT srp.*,pc.title,pc.format,mp.brand_id,mp.month_start,b.display_name AS brand_name,
                          pbp.monthly_soft_limit,pbp.monthly_hard_limit,pbp.default_content_limit,
                          pbp.approval_threshold,pbp.currency
                   FROM football_brief.shot_routing_plans srp
                   JOIN football_brief.portfolio_content pc ON pc.id=srp.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   JOIN football_brief.production_budget_policies pbp ON pbp.id=srp.budget_policy_id
                   WHERE srp.id=%s""",
                (plan_id,),
            ).fetchone()
            if not plan:
                raise RoutingSpendError("routing_plan_not_found")
            items = conn.execute(
                """SELECT sri.*,vs.sequence,vc.asset_id,rp.request_payload,rp.estimated_cost AS quoted_cost,
                          rce.provider_key,rce.model_key,rce.quality_rating,rce.health_status
                   FROM football_brief.shot_routing_items sri
                   JOIN football_brief.visual_shots vs ON vs.id=sri.visual_shot_id
                   LEFT JOIN football_brief.visual_candidates vc ON vc.id=sri.selected_candidate_id
                   LEFT JOIN football_brief.renderer_preflight_records rp ON rp.id=sri.renderer_preflight_id
                   LEFT JOIN football_brief.renderer_catalogue_entries rce ON rce.id=rp.renderer_catalogue_entry_id
                   WHERE sri.routing_plan_id=%s ORDER BY vs.sequence""",
                (plan_id,),
            ).fetchall()
            decisions = conn.execute(
                "SELECT * FROM football_brief.production_spend_decisions WHERE routing_plan_id=%s ORDER BY created_at,id",
                (plan_id,),
            ).fetchall()
            reservations = conn.execute(
                """SELECT psr.*,gj.status AS job_status,gj.actual_cost_usd AS job_actual_cost
                   FROM football_brief.production_spend_reservations psr
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=psr.generation_job_id
                   WHERE psr.routing_plan_id=%s ORDER BY psr.created_at,psr.id""",
                (plan_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT * FROM football_brief.production_spend_events WHERE routing_plan_id=%s ORDER BY created_at,id",
                (plan_id,),
            ).fetchall()
        return {
            "ok": True,
            "plan": dict(plan),
            "items": [dict(item) for item in items],
            "decisions": [dict(item) for item in decisions],
            "reservations": [dict(item) for item in reservations],
            "events": [dict(item) for item in events],
        }

    @staticmethod
    def _recommend_route(
        routing_input: ShotRoutingInput,
        preflight: Any,
    ) -> tuple[ShotRoute, str, list[dict[str, Any]]]:
        available_managed = bool(preflight and preflight["accepted"])
        alternatives: list[dict[str, Any]] = []
        if routing_input.forced_route:
            route = routing_input.forced_route
            if route == ShotRoute.MANAGED_RENDER and not available_managed:
                raise RoutingSpendError("forced_managed_route_requires_accepted_preflight")
            return route, routing_input.override_rationale or "Explicit operator override", [
                {"route": "automatic_recommendation", "reason": "Operator override recorded separately"}
            ]

        if routing_input.factual_control_requirement >= 75 and routing_input.motion_complexity <= 60:
            route = ShotRoute.DETERMINISTIC_ANIMATION
            rationale = "High factual-control need with bounded motion favors deterministic animation."
        elif (
            routing_input.local_preview_quality >= 75
            and routing_input.realism_requirement < 75
            and routing_input.motion_complexity < 70
        ):
            route = ShotRoute.LOCAL_RENDER
            rationale = "Approved local quality is sufficient for the required realism and motion."
        elif available_managed and (
            routing_input.hero_importance >= 65
            or routing_input.realism_requirement >= 70
            or routing_input.motion_complexity >= 70
            or routing_input.engagement_contribution >= 75
        ):
            route = ShotRoute.MANAGED_RENDER
            rationale = "A high-value realism, motion, hero, or engagement requirement justifies managed rendering."
        else:
            route = ShotRoute.MANUAL_EDIT
            rationale = "No automated route satisfies the current quality and control requirements."

        if route != ShotRoute.DETERMINISTIC_ANIMATION:
            alternatives.append({"route": ShotRoute.DETERMINISTIC_ANIMATION.value, "reason": "Use when factual control outweighs realism."})
        if route != ShotRoute.LOCAL_RENDER:
            alternatives.append({"route": ShotRoute.LOCAL_RENDER.value, "reason": "Zero-cost when approved local quality is sufficient."})
        if route != ShotRoute.MANAGED_RENDER and available_managed:
            alternatives.append({"route": ShotRoute.MANAGED_RENDER.value, "reason": "Available with explicit spend approval."})
        if route != ShotRoute.MANUAL_EDIT:
            alternatives.append({"route": ShotRoute.MANUAL_EDIT.value, "reason": "Fallback when generation cannot satisfy control requirements."})
        return route, rationale, alternatives

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not row:
            raise RoutingSpendError("operator_inactive_or_missing")
