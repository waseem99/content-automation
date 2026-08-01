from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


ROUTER_VERSION = "p126-hybrid-router-v1"
ROUTE_CLASSES = (
    "reuse_asset",
    "deterministic_composition",
    "local_generation",
    "cloud_portable",
    "premium_low_cost",
    "premium_hero",
    "manual_edit",
)
PAID_ROUTE_CLASSES = frozenset({"cloud_portable", "premium_low_cost", "premium_hero"})
TERMINAL_ATTEMPT_STATES = frozenset({"succeeded", "failed", "cancelled", "accepted", "rejected"})


class HybridRoutingError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _plain(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def _pricing_per_second(pricing: dict[str, Any]) -> Decimal:
    for key in (
        "cost_per_accepted_second",
        "cost_per_second",
        "per_second",
        "unit_cost_per_second",
    ):
        if pricing.get(key) is not None:
            return max(Decimal("0"), _decimal(pricing[key]))
    if pricing.get("per_minute") is not None:
        return max(Decimal("0"), _decimal(pricing["per_minute"]) / Decimal("60"))
    if pricing.get("flat_cost") is not None:
        return max(Decimal("0"), _decimal(pricing["flat_cost"]))
    return Decimal("0")


def _eta_seconds(payload: dict[str, Any], default: int) -> int:
    for key in ("p50_seconds", "p50", "expected_seconds", "seconds"):
        if payload.get(key) is not None:
            try:
                return max(0, int(payload[key]))
            except (TypeError, ValueError):
                pass
    return default


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


class HybridRoutingService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def configure_policy(
        self,
        *,
        brand_id: UUID,
        actor: str,
        maximum_content_cost: Decimal = Decimal("0"),
        maximum_scene_cost: Decimal = Decimal("0"),
        default_quality_floor: float = 75,
        hero_quality_floor: float = 86,
        maximum_attempts: int = 3,
        scoring_weights: dict[str, float] | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        maximum_content_cost = max(Decimal("0"), _decimal(maximum_content_cost))
        maximum_scene_cost = max(Decimal("0"), _decimal(maximum_scene_cost))
        if maximum_content_cost and maximum_scene_cost > maximum_content_cost:
            raise HybridRoutingError("scene_ceiling_exceeds_content_ceiling")
        if not 1 <= maximum_attempts <= 10:
            raise HybridRoutingError("maximum_attempts_out_of_range")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            brand = conn.execute(
                "SELECT id FROM football_brief.brands WHERE id=%s AND active=true",
                (brand_id,),
            ).fetchone()
            if not brand:
                raise HybridRoutingError("brand_not_found")
            active = conn.execute(
                """SELECT * FROM football_brief.hybrid_routing_policies
                   WHERE brand_id=%s AND status='active' FOR UPDATE""",
                (brand_id,),
            ).fetchone()
            version = 1
            parent_id = None
            if active:
                version = int(active["version"]) + 1
                parent_id = active["id"]
                conn.execute(
                    """UPDATE football_brief.hybrid_routing_policies
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, active["id"]),
                )
            policy = conn.execute(
                """INSERT INTO football_brief.hybrid_routing_policies
                   (brand_id,version,parent_policy_id,status,default_quality_floor,
                    hero_quality_floor,maximum_content_cost,maximum_scene_cost,
                    maximum_attempts,scoring_weights,configuration,created_by,
                    activated_by,activated_at)
                   VALUES (%s,%s,%s,'active',%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                           %s,%s,now()) RETURNING *""",
                (
                    brand_id,
                    version,
                    parent_id,
                    default_quality_floor,
                    hero_quality_floor,
                    maximum_content_cost,
                    maximum_scene_cost,
                    maximum_attempts,
                    _json(scoring_weights or {}),
                    _json(configuration or {}),
                    actor,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "kind": "hybrid_routing_policy", "policy": _plain(dict(policy))}

    def register_template(
        self,
        *,
        template_key: str,
        category: str,
        specification: dict[str, Any],
        actor: str,
        brand_id: UUID | None = None,
        asset_id: UUID | None = None,
        duration_seconds: float | None = None,
        quality_rating: float = 85,
        supported_formats: list[str] | None = None,
        supported_territories: list[str] | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        if category not in {
            "intro",
            "outro",
            "caption",
            "background",
            "transition",
            "map",
            "diagram",
            "brand_treatment",
            "reusable_asset",
        }:
            raise HybridRoutingError("invalid_template_category")
        if not template_key or len(template_key) > 120:
            raise HybridRoutingError("invalid_template_key")
        digest = _sha(specification)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            if brand_id:
                brand = conn.execute(
                    "SELECT id FROM football_brief.brands WHERE id=%s AND active=true",
                    (brand_id,),
                ).fetchone()
                if not brand:
                    raise HybridRoutingError("brand_not_found")
            if asset_id:
                asset = conn.execute(
                    """SELECT a.id,EXISTS(
                           SELECT 1 FROM football_brief.asset_storage_locations location
                           WHERE location.asset_id=a.id AND location.status='available'
                       ) AS available
                       FROM football_brief.assets a WHERE a.id=%s AND a.lifecycle_status='approved'""",
                    (asset_id,),
                ).fetchone()
                if not asset:
                    raise HybridRoutingError("approved_template_asset_required")
                if activate and not asset["available"]:
                    raise HybridRoutingError("available_template_asset_location_required")
            active = conn.execute(
                """SELECT * FROM football_brief.hybrid_production_templates
                   WHERE brand_id IS NOT DISTINCT FROM %s AND template_key=%s AND category=%s
                     AND status='active' FOR UPDATE""",
                (brand_id, template_key, category),
            ).fetchone()
            version = 1
            parent_id = None
            if active:
                version = int(active["version"]) + 1
                parent_id = active["id"]
                conn.execute(
                    """UPDATE football_brief.hybrid_production_templates
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, active["id"]),
                )
            status = "active" if activate else "draft"
            row = conn.execute(
                """INSERT INTO football_brief.hybrid_production_templates
                   (brand_id,template_key,category,version,parent_template_id,status,
                    asset_id,duration_seconds,quality_rating,supported_formats,
                    supported_territories,specification,specification_sha256,created_by,
                    activated_by,activated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                           CASE WHEN %s='active' THEN %s ELSE NULL END,
                           CASE WHEN %s='active' THEN now() ELSE NULL END)
                   RETURNING *""",
                (
                    brand_id,
                    template_key,
                    category,
                    version,
                    parent_id,
                    status,
                    asset_id,
                    duration_seconds,
                    quality_rating,
                    supported_formats or [],
                    supported_territories or ["global"],
                    _json(specification),
                    digest,
                    actor,
                    status,
                    actor,
                    status,
                ),
            ).fetchone()
        return {"ok": True, "kind": "hybrid_production_template", "template": _plain(dict(row))}

    def record_measurement(
        self,
        *,
        measurement_key: str,
        route_class: str,
        actor: str,
        acceptance_rate: float,
        quality_score: float,
        evidence: dict[str, Any],
        observed_at: datetime,
        cost_per_accepted_second: Decimal = Decimal("0"),
        queue_eta_p50_seconds: int = 0,
        queue_eta_p95_seconds: int = 0,
        continuity_risk: float = 0,
        hardware_available: bool = True,
        sample_size: int = 0,
        supported_territories: list[str] | None = None,
        renderer_catalogue_entry_id: UUID | None = None,
        local_video_workflow_id: UUID | None = None,
        template_id: UUID | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        if route_class not in ROUTE_CLASSES:
            raise HybridRoutingError("invalid_route_class")
        digest = _sha(evidence)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            active = conn.execute(
                """SELECT * FROM football_brief.hybrid_renderer_measurements
                   WHERE measurement_key=%s AND status='active' FOR UPDATE""",
                (measurement_key,),
            ).fetchone()
            version = 1
            parent_id = None
            if active:
                version = int(active["version"]) + 1
                parent_id = active["id"]
                conn.execute(
                    """UPDATE football_brief.hybrid_renderer_measurements
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, active["id"]),
                )
            status = "active" if activate else "draft"
            row = conn.execute(
                """INSERT INTO football_brief.hybrid_renderer_measurements
                   (measurement_key,version,parent_measurement_id,status,route_class,
                    renderer_catalogue_entry_id,local_video_workflow_id,template_id,
                    acceptance_rate,cost_per_accepted_second,queue_eta_p50_seconds,
                    queue_eta_p95_seconds,quality_score,continuity_risk,hardware_available,
                    sample_size,supported_territories,evidence,evidence_digest,observed_at,
                    created_by,activated_by,activated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           %s::jsonb,%s,%s,%s,
                           CASE WHEN %s='active' THEN %s ELSE NULL END,
                           CASE WHEN %s='active' THEN now() ELSE NULL END)
                   RETURNING *""",
                (
                    measurement_key,
                    version,
                    parent_id,
                    status,
                    route_class,
                    renderer_catalogue_entry_id,
                    local_video_workflow_id,
                    template_id,
                    acceptance_rate,
                    cost_per_accepted_second,
                    queue_eta_p50_seconds,
                    max(queue_eta_p50_seconds, queue_eta_p95_seconds),
                    quality_score,
                    continuity_risk,
                    hardware_available,
                    sample_size,
                    supported_territories or ["global"],
                    _json(evidence),
                    digest,
                    observed_at,
                    actor,
                    status,
                    actor,
                    status,
                ),
            ).fetchone()
        return {"ok": True, "kind": "hybrid_renderer_measurement", "measurement": _plain(dict(row))}

    def plan_package(
        self,
        *,
        package_id: UUID,
        actor: str,
        deadline_at: datetime | None = None,
    ) -> dict[str, Any]:
        deadline = deadline_at or (datetime.now(timezone.utc) + timedelta(hours=48))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            context = self._package_context(conn, package_id, for_update=True)
            package = dict(context["package"] or {})
            if package.get("schema") != "ready-for-final-video-generation/v1":
                raise HybridRoutingError("unsupported_pre_generation_package_schema")
            if context["package_status"] != "ready" or context["item_state"] != "ready_for_final_video_generation":
                raise HybridRoutingError("ready_pre_generation_package_required")
            live = conn.execute(
                """SELECT * FROM football_brief.hybrid_route_plans
                   WHERE pre_generation_package_id=%s
                     AND status IN ('ready','approval_required','blocked','executing')
                   FOR UPDATE""",
                (package_id,),
            ).fetchone()
            policy = self._ensure_policy(conn, brand_id=context["brand_id"], actor=actor)
            if live and live["package_sha256"] == context["package_sha256"] and live["routing_policy_id"] == policy["id"]:
                return self._detail_locked(conn, UUID(str(live["id"])))

            budget = self._active_budget_policy(
                conn,
                portfolio_content_id=context["portfolio_content_id"],
            )
            edl, corrected = self._build_edl(package)
            resources = self._routing_resources(
                conn,
                brand_id=context["brand_id"],
                package=package,
            )
            policy_order = list(policy["routing_order"] or ROUTE_CLASSES)
            weights = self._weights(dict(policy["scoring_weights"] or {}))
            scene_specs: list[dict[str, Any]] = []
            route_seconds = {route: Decimal("0") for route in ROUTE_CLASSES}
            estimated_cost = Decimal("0")
            paid_selected = False
            blocked = False
            for scene in edl:
                hero = self._is_hero(scene, len(edl))
                quality_floor = float(
                    policy["hero_quality_floor"] if hero else policy["default_quality_floor"]
                )
                candidates = self._candidate_specs(
                    scene=scene,
                    package=package,
                    policy=policy,
                    policy_order=policy_order,
                    weights=weights,
                    quality_floor=quality_floor,
                    deadline=deadline,
                    budget=budget,
                    resources=resources,
                )
                candidates.sort(
                    key=lambda item: (
                        policy_order.index(item["route_class"]),
                        0 if item["eligible"] else 1,
                        -float(item["score"]),
                        float(item["estimated_cost"]),
                        item["identity_key"],
                    )
                )
                for rank, candidate in enumerate(candidates, start=1):
                    candidate["rank"] = rank
                selected = next((item for item in candidates if item["eligible"]), None)
                if selected is None:
                    blocked = True
                else:
                    route_seconds[selected["route_class"]] += _decimal(scene["duration_seconds"])
                    estimated_cost += _decimal(selected["estimated_cost"])
                    paid_selected = paid_selected or bool(selected["requires_spend_approval"])
                scene_specs.append(
                    {
                        **scene,
                        "hero": hero,
                        "quality_floor": quality_floor,
                        "maximum_attempts": int(policy["maximum_attempts"]),
                        "maximum_cost": _decimal(policy["maximum_scene_cost"]),
                        "continuity_group": self._continuity_group(scene, package),
                        "bindings": dict(scene.get("continuity_bindings") or {}),
                        "keyframe_requirements": self._keyframe_requirements(scene),
                        "motion_intensity": self._motion_intensity(scene),
                        "candidates": candidates,
                        "selected_identity": selected["identity_key"] if selected else None,
                    }
                )

            content_ceiling = _decimal(policy["maximum_content_cost"])
            ceiling_exceeded = bool(content_ceiling and estimated_cost > content_ceiling)
            status = "blocked" if blocked or ceiling_exceeded else "approval_required" if paid_selected else "ready"
            scoring_snapshot = {
                "router_version": ROUTER_VERSION,
                "routing_policy_id": str(policy["id"]),
                "routing_order": policy_order,
                "weights": weights,
                "timeline_corrected": corrected,
                "paid_execution_enabled": False,
                "automatic_public_publishing": False,
                "content_ceiling_exceeded": ceiling_exceeded,
                "active_budget_policy_id": str(budget["id"]) if budget else None,
            }
            plan_snapshot = {
                "package_sha256": context["package_sha256"],
                "deadline_at": deadline.isoformat(),
                "status": status,
                "estimated_cost": str(estimated_cost),
                "route_seconds": {key: str(value) for key, value in route_seconds.items()},
                "scenes": [
                    {
                        "shot_id": scene["shot_id"],
                        "start": scene["start_seconds"],
                        "end": scene["end_seconds"],
                        "selected": scene["selected_identity"],
                        "fallback": [item["identity_key"] for item in scene["candidates"]],
                    }
                    for scene in scene_specs
                ],
                "scoring": scoring_snapshot,
            }
            version_number = 1
            parent_id = None
            if live:
                version_number = int(live["version"]) + 1
                parent_id = live["id"]
                conn.execute(
                    """UPDATE football_brief.hybrid_route_plans
                       SET status='superseded',superseded_at=now() WHERE id=%s""",
                    (live["id"],),
                )
            plan = conn.execute(
                """INSERT INTO football_brief.hybrid_route_plans
                   (pre_generation_package_id,campaign_item_id,portfolio_content_id,
                    routing_policy_id,budget_policy_id,version,parent_plan_id,status,
                    package_sha256,plan_sha256,exact_duration_seconds,estimated_cost,
                    deadline_at,route_seconds,scoring_snapshot,package_snapshot,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s) RETURNING *""",
                (
                    package_id,
                    context["campaign_item_id"],
                    context["portfolio_content_id"],
                    policy["id"],
                    budget["id"] if budget else None,
                    version_number,
                    parent_id,
                    status,
                    context["package_sha256"],
                    _sha(plan_snapshot),
                    sum(_decimal(scene["duration_seconds"]) for scene in edl),
                    estimated_cost,
                    deadline,
                    _json({key: float(value) for key, value in route_seconds.items()}),
                    _json(scoring_snapshot),
                    _json(package),
                    actor,
                ),
            ).fetchone()
            for scene in scene_specs:
                scene_row = conn.execute(
                    """INSERT INTO football_brief.hybrid_route_scenes
                       (route_plan_id,shot_id,scene_key,sequence,start_seconds,end_seconds,
                        duration_seconds,render_class,status,continuity_group,bindings,
                        keyframe_requirements,motion_intensity,quality_floor,deadline_at,
                        maximum_attempts,maximum_cost,fallback_chain,rationale)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,
                               %s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                    (
                        plan["id"],
                        scene["shot_id"],
                        scene["scene_key"],
                        scene["sequence"],
                        scene["start_seconds"],
                        scene["end_seconds"],
                        scene["duration_seconds"],
                        next(
                            (
                                item["route_class"]
                                for item in scene["candidates"]
                                if item["identity_key"] == scene["selected_identity"]
                            ),
                            "manual_edit",
                        ),
                        "blocked" if scene["selected_identity"] is None else "approval_required"
                        if next(
                            (
                                item["requires_spend_approval"]
                                for item in scene["candidates"]
                                if item["identity_key"] == scene["selected_identity"]
                            ),
                            False,
                        )
                        else "planned",
                        scene["continuity_group"],
                        _json(scene["bindings"]),
                        _json(scene["keyframe_requirements"]),
                        scene["motion_intensity"],
                        scene["quality_floor"],
                        deadline,
                        scene["maximum_attempts"],
                        scene["maximum_cost"],
                        _json(
                            [
                                {
                                    "rank": item["rank"],
                                    "identity_key": item["identity_key"],
                                    "route_class": item["route_class"],
                                    "eligible": item["eligible"],
                                    "requires_spend_approval": item["requires_spend_approval"],
                                }
                                for item in scene["candidates"]
                            ]
                        ),
                        self._scene_rationale(scene),
                    ),
                ).fetchone()
                selected_candidate_id = None
                for candidate in scene["candidates"]:
                    candidate_row = conn.execute(
                        """INSERT INTO football_brief.hybrid_route_candidates
                           (route_scene_id,rank,route_class,renderer_catalogue_entry_id,
                            local_video_workflow_id,template_id,measurement_id,eligible,
                            requires_spend_approval,score,estimated_cost,expected_eta_seconds,
                            acceptance_rate,quality_score,continuity_risk,rejection_reasons,
                            scoring_evidence)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                   %s::jsonb,%s::jsonb) RETURNING *""",
                        (
                            scene_row["id"],
                            candidate["rank"],
                            candidate["route_class"],
                            candidate.get("renderer_catalogue_entry_id"),
                            candidate.get("local_video_workflow_id"),
                            candidate.get("template_id"),
                            candidate.get("measurement_id"),
                            candidate["eligible"],
                            candidate["requires_spend_approval"],
                            candidate["score"],
                            candidate["estimated_cost"],
                            candidate["expected_eta_seconds"],
                            candidate["acceptance_rate"],
                            candidate["quality_score"],
                            candidate["continuity_risk"],
                            _json(candidate["rejection_reasons"]),
                            _json(candidate["scoring_evidence"]),
                        ),
                    ).fetchone()
                    if candidate["identity_key"] == scene["selected_identity"]:
                        selected_candidate_id = candidate_row["id"]
                if selected_candidate_id:
                    conn.execute(
                        """UPDATE football_brief.hybrid_route_scenes
                           SET selected_candidate_id=%s WHERE id=%s""",
                        (selected_candidate_id, scene_row["id"]),
                    )
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,event_type,actor,details)
                   VALUES (%s,'plan_created',%s,%s::jsonb)""",
                (
                    plan["id"],
                    actor,
                    _json(
                        {
                            "router_version": ROUTER_VERSION,
                            "status": status,
                            "exact_duration_seconds": float(plan["exact_duration_seconds"]),
                            "estimated_cost": float(estimated_cost),
                            "timeline_corrected": corrected,
                            "automatic_paid_execution": False,
                        }
                    ),
                ),
            )
            return self._detail_locked(conn, UUID(str(plan["id"])))

    def detail(self, *, plan_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            return self._detail_locked(conn, plan_id)

    def report(self, *, plan_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            plan = conn.execute(
                "SELECT * FROM football_brief.hybrid_route_plans WHERE id=%s",
                (plan_id,),
            ).fetchone()
            if not plan:
                raise HybridRoutingError("hybrid_route_plan_not_found")
            scenes = conn.execute(
                """SELECT scene.*,candidate.route_class AS selected_route_class
                   FROM football_brief.hybrid_route_scenes scene
                   LEFT JOIN football_brief.hybrid_route_candidates candidate
                     ON candidate.id=scene.selected_candidate_id
                   WHERE scene.route_plan_id=%s ORDER BY scene.sequence""",
                (plan_id,),
            ).fetchall()
            attempts = conn.execute(
                """SELECT attempt.*,candidate.route_class
                   FROM football_brief.hybrid_route_attempts attempt
                   JOIN football_brief.hybrid_route_candidates candidate ON candidate.id=attempt.candidate_id
                   JOIN football_brief.hybrid_route_scenes scene ON scene.id=attempt.route_scene_id
                   WHERE scene.route_plan_id=%s ORDER BY scene.sequence,attempt.attempt_number""",
                (plan_id,),
            ).fetchall()
        accepted = [row for row in attempts if row["status"] == "accepted"]
        failed = [row for row in attempts if row["status"] in {"failed", "rejected"}]
        accepted_by_route = {route: Decimal("0") for route in ROUTE_CLASSES}
        for row in accepted:
            accepted_by_route[str(row["route_class"])] += _decimal(row["accepted_seconds"])
        retry_seconds = sum(_decimal(row["rendered_seconds"]) for row in failed)
        generated_routes = {"local_generation", "cloud_portable", "premium_low_cost", "premium_hero"}
        generated_seconds = sum(
            value for key, value in accepted_by_route.items() if key in generated_routes
        )
        deterministic_reused = accepted_by_route["reuse_asset"] + accepted_by_route["deterministic_composition"]
        actual_cost = sum(_decimal(row["actual_cost"]) for row in attempts)
        payload = {
            "ok": True,
            "kind": "hybrid_route_report",
            "plan": _plain(dict(plan)),
            "scene_count": len(scenes),
            "finished_seconds": float(sum(_decimal(row["accepted_seconds"]) for row in accepted)),
            "generated_seconds": float(generated_seconds),
            "retry_seconds": float(retry_seconds),
            "accepted_local_seconds": float(accepted_by_route["local_generation"]),
            "accepted_cloud_seconds": float(accepted_by_route["cloud_portable"]),
            "accepted_premium_seconds": float(
                accepted_by_route["premium_low_cost"] + accepted_by_route["premium_hero"]
            ),
            "deterministic_reused_seconds": float(deterministic_reused),
            "manual_edit_seconds": float(accepted_by_route["manual_edit"]),
            "actual_cost": float(actual_cost),
            "planned_route_seconds": _plain(dict(plan["route_seconds"] or {})),
            "automatic_paid_execution": False,
            "public_publishing": False,
        }
        return payload

    def override_scene(
        self,
        *,
        scene_id: UUID,
        candidate_id: UUID,
        rationale: str,
        actor: str,
    ) -> dict[str, Any]:
        if len(rationale.strip()) < 5:
            raise HybridRoutingError("override_rationale_required")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            scene = conn.execute(
                """SELECT scene.*,plan.status AS plan_status
                   FROM football_brief.hybrid_route_scenes scene
                   JOIN football_brief.hybrid_route_plans plan ON plan.id=scene.route_plan_id
                   WHERE scene.id=%s FOR UPDATE""",
                (scene_id,),
            ).fetchone()
            if not scene:
                raise HybridRoutingError("hybrid_route_scene_not_found")
            if scene["status"] in {"accepted", "running"}:
                raise HybridRoutingError("hybrid_route_scene_not_overridable")
            candidate = conn.execute(
                "SELECT * FROM football_brief.hybrid_route_candidates WHERE id=%s AND route_scene_id=%s",
                (candidate_id, scene_id),
            ).fetchone()
            if not candidate:
                raise HybridRoutingError("hybrid_route_candidate_not_found")
            if not candidate["eligible"]:
                raise HybridRoutingError(
                    "ineligible_route_candidate",
                    details={"rejection_reasons": _plain(candidate["rejection_reasons"])},
                )
            previous = scene["selected_candidate_id"]
            if previous == candidate_id:
                return self._detail_locked(conn, UUID(str(scene["route_plan_id"])))
            if not previous:
                raise HybridRoutingError("previous_route_candidate_missing")
            status = "approval_required" if candidate["requires_spend_approval"] else "planned"
            conn.execute(
                """UPDATE football_brief.hybrid_route_scenes
                   SET selected_candidate_id=%s,render_class=%s,status=%s WHERE id=%s""",
                (candidate_id, candidate["route_class"], status, scene_id),
            )
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_overrides
                   (route_scene_id,previous_candidate_id,selected_candidate_id,rationale,actor)
                   VALUES (%s,%s,%s,%s,%s)""",
                (scene_id, previous, candidate_id, rationale.strip(), actor),
            )
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,route_scene_id,event_type,actor,details)
                   VALUES (%s,%s,'route_overridden',%s,%s::jsonb)""",
                (
                    scene["route_plan_id"],
                    scene_id,
                    actor,
                    _json(
                        {
                            "previous_candidate_id": str(previous),
                            "selected_candidate_id": str(candidate_id),
                            "rationale": rationale.strip(),
                        }
                    ),
                ),
            )
            self._refresh_plan_status(conn, UUID(str(scene["route_plan_id"])))
            return self._detail_locked(conn, UUID(str(scene["route_plan_id"])))

    def record_spend_decision(
        self,
        *,
        plan_id: UUID,
        decision: str,
        approved_ceiling: Decimal | None,
        rationale: str,
        actor: str,
    ) -> dict[str, Any]:
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise HybridRoutingError("invalid_spend_decision")
        if len(rationale.strip()) < 3:
            raise HybridRoutingError("spend_rationale_required")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            plan = conn.execute(
                "SELECT * FROM football_brief.hybrid_route_plans WHERE id=%s FOR UPDATE",
                (plan_id,),
            ).fetchone()
            if not plan:
                raise HybridRoutingError("hybrid_route_plan_not_found")
            if not plan["budget_policy_id"]:
                raise HybridRoutingError("active_budget_policy_required")
            policy = conn.execute(
                """SELECT * FROM football_brief.production_budget_policies
                   WHERE id=%s AND status='active' FOR UPDATE""",
                (plan["budget_policy_id"],),
            ).fetchone()
            if not policy:
                raise HybridRoutingError("active_budget_policy_required")
            existing = conn.execute(
                "SELECT * FROM football_brief.hybrid_spend_approvals WHERE route_plan_id=%s",
                (plan_id,),
            ).fetchone()
            if existing:
                return {"ok": True, "kind": "hybrid_spend_decision", "approval": _plain(dict(existing))}
            ceiling = _decimal(approved_ceiling) if approved_ceiling is not None else None
            if decision == "approved":
                if ceiling is None:
                    raise HybridRoutingError("approved_spend_ceiling_required")
                if ceiling < _decimal(plan["estimated_cost"]):
                    raise HybridRoutingError("approved_ceiling_below_plan_estimate")
                content_limit = _decimal(policy["default_content_limit"])
                if content_limit and ceiling > content_limit:
                    raise HybridRoutingError("approved_ceiling_exceeds_content_limit")
                committed = self._monthly_committed(conn, policy=policy, exclude_plan_id=plan_id)
                available = _decimal(policy["monthly_hard_limit"]) - committed
                if ceiling > available:
                    raise HybridRoutingError(
                        "approved_ceiling_exceeds_monthly_available",
                        details={"available": float(max(Decimal("0"), available))},
                    )
            approval = conn.execute(
                """INSERT INTO football_brief.hybrid_spend_approvals
                   (route_plan_id,budget_policy_id,decision,approved_ceiling,
                    reviewer_operator_id,rationale)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (plan_id, policy["id"], decision, ceiling, actor, rationale.strip()),
            ).fetchone()
            new_status = "ready" if decision == "approved" else "approval_required" if decision == "changes_requested" else "blocked"
            conn.execute(
                "UPDATE football_brief.hybrid_route_plans SET status=%s WHERE id=%s",
                (new_status, plan_id),
            )
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,event_type,actor,details)
                   VALUES (%s,'spend_decision',%s,%s::jsonb)""",
                (
                    plan_id,
                    actor,
                    _json(
                        {
                            "decision": decision,
                            "approved_ceiling": float(ceiling) if ceiling is not None else None,
                            "budget_policy_id": str(policy["id"]),
                        }
                    ),
                ),
            )
            return {"ok": True, "kind": "hybrid_spend_decision", "approval": _plain(dict(approval))}

    def create_attempt(
        self,
        *,
        scene_id: UUID,
        candidate_id: UUID,
        billing_key: str,
        actor: str,
    ) -> dict[str, Any]:
        if len(billing_key.strip()) < 8:
            raise HybridRoutingError("billing_key_too_short")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            existing = conn.execute(
                "SELECT * FROM football_brief.hybrid_route_attempts WHERE billing_key=%s",
                (billing_key.strip(),),
            ).fetchone()
            if existing:
                if existing["route_scene_id"] != scene_id or existing["candidate_id"] != candidate_id:
                    raise HybridRoutingError("billing_key_identity_mismatch")
                return {"ok": True, "kind": "hybrid_route_attempt", "idempotent": True, "attempt": _plain(dict(existing))}
            scene = conn.execute(
                """SELECT scene.*,plan.status AS plan_status,plan.routing_policy_id,
                          plan.budget_policy_id,plan.estimated_cost AS plan_estimated_cost
                   FROM football_brief.hybrid_route_scenes scene
                   JOIN football_brief.hybrid_route_plans plan ON plan.id=scene.route_plan_id
                   WHERE scene.id=%s FOR UPDATE""",
                (scene_id,),
            ).fetchone()
            if not scene:
                raise HybridRoutingError("hybrid_route_scene_not_found")
            if scene["status"] in {"accepted", "running", "cancelled"}:
                raise HybridRoutingError("hybrid_route_scene_not_attemptable")
            candidate = conn.execute(
                "SELECT * FROM football_brief.hybrid_route_candidates WHERE id=%s AND route_scene_id=%s",
                (candidate_id, scene_id),
            ).fetchone()
            if not candidate:
                raise HybridRoutingError("hybrid_route_candidate_not_found")
            if candidate_id != scene["selected_candidate_id"]:
                raise HybridRoutingError("candidate_must_be_selected_before_attempt")
            if not candidate["eligible"]:
                raise HybridRoutingError("ineligible_route_candidate")
            attempts = int(
                conn.execute(
                    "SELECT count(*)::int AS value FROM football_brief.hybrid_route_attempts WHERE route_scene_id=%s",
                    (scene_id,),
                ).fetchone()["value"]
            )
            if attempts >= int(scene["maximum_attempts"]):
                raise HybridRoutingError("maximum_scene_attempts_reached")
            approval_id = None
            if candidate["requires_spend_approval"] or candidate["route_class"] in PAID_ROUTE_CLASSES:
                approval = conn.execute(
                    """SELECT * FROM football_brief.hybrid_spend_approvals
                       WHERE route_plan_id=%s AND decision='approved'""",
                    (scene["route_plan_id"],),
                ).fetchone()
                if not approval:
                    raise HybridRoutingError("explicit_spend_approval_required")
                approval_id = approval["id"]
                spent = _decimal(
                    conn.execute(
                        """SELECT COALESCE(sum(actual_cost),0) AS value
                           FROM football_brief.hybrid_route_attempts attempt
                           JOIN football_brief.hybrid_route_scenes child
                             ON child.id=attempt.route_scene_id
                           WHERE child.route_plan_id=%s""",
                        (scene["route_plan_id"],),
                    ).fetchone()["value"]
                )
                if spent + _decimal(candidate["estimated_cost"]) > _decimal(approval["approved_ceiling"]):
                    raise HybridRoutingError("attempt_exceeds_approved_spend_ceiling")
                policy = conn.execute(
                    "SELECT * FROM football_brief.hybrid_routing_policies WHERE id=%s",
                    (scene["routing_policy_id"],),
                ).fetchone()
                if policy and policy["cloud_requires_local_miss"] and candidate["route_class"] in PAID_ROUTE_CLASSES:
                    prior_local = conn.execute(
                        """SELECT candidate.id
                           FROM football_brief.hybrid_route_candidates candidate
                           WHERE candidate.route_scene_id=%s
                             AND candidate.route_class='local_generation'
                             AND candidate.eligible=true AND candidate.rank < %s""",
                        (scene_id, candidate["rank"]),
                    ).fetchall()
                    for local in prior_local:
                        exhausted = conn.execute(
                            """SELECT 1 FROM football_brief.hybrid_route_attempts
                               WHERE route_scene_id=%s AND candidate_id=%s
                                 AND status IN ('failed','rejected','cancelled')""",
                            (scene_id, local["id"]),
                        ).fetchone()
                        if not exhausted:
                            raise HybridRoutingError("local_route_not_exhausted")
            attempt = conn.execute(
                """INSERT INTO football_brief.hybrid_route_attempts
                   (route_scene_id,candidate_id,attempt_number,billing_key,spend_approval_id,
                    status,quoted_cost,created_by)
                   VALUES (%s,%s,%s,%s,%s,'planned',%s,%s) RETURNING *""",
                (
                    scene_id,
                    candidate_id,
                    attempts + 1,
                    billing_key.strip(),
                    approval_id,
                    candidate["estimated_cost"],
                    actor,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE football_brief.hybrid_route_scenes SET status='queued' WHERE id=%s",
                (scene_id,),
            )
            conn.execute(
                "UPDATE football_brief.hybrid_route_plans SET status='executing' WHERE id=%s",
                (scene["route_plan_id"],),
            )
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,route_scene_id,event_type,actor,details)
                   VALUES (%s,%s,'attempt_created',%s,%s::jsonb)""",
                (
                    scene["route_plan_id"],
                    scene_id,
                    actor,
                    _json(
                        {
                            "attempt_id": str(attempt["id"]),
                            "candidate_id": str(candidate_id),
                            "billing_key": billing_key.strip(),
                            "provider_submission": False,
                            "generation_job_created": False,
                        }
                    ),
                ),
            )
            return {"ok": True, "kind": "hybrid_route_attempt", "idempotent": False, "attempt": _plain(dict(attempt))}

    def complete_attempt(
        self,
        *,
        attempt_id: UUID,
        status: str,
        rendered_seconds: float,
        accepted_seconds: float,
        actual_cost: Decimal,
        actor: str,
        failure_code: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"accepted", "failed", "rejected", "cancelled"}:
            raise HybridRoutingError("invalid_attempt_terminal_status")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            attempt = conn.execute(
                """SELECT attempt.*,candidate.route_class,candidate.rank,candidate.requires_spend_approval,
                          scene.route_plan_id,scene.duration_seconds,scene.maximum_attempts
                   FROM football_brief.hybrid_route_attempts attempt
                   JOIN football_brief.hybrid_route_candidates candidate ON candidate.id=attempt.candidate_id
                   JOIN football_brief.hybrid_route_scenes scene ON scene.id=attempt.route_scene_id
                   WHERE attempt.id=%s FOR UPDATE OF attempt""",
                (attempt_id,),
            ).fetchone()
            if not attempt:
                raise HybridRoutingError("hybrid_route_attempt_not_found")
            if attempt["status"] in TERMINAL_ATTEMPT_STATES:
                return {"ok": True, "kind": "hybrid_route_attempt_completed", "idempotent": True, "attempt": _plain(dict(attempt))}
            rendered = _decimal(rendered_seconds)
            accepted = _decimal(accepted_seconds)
            cost = _decimal(actual_cost)
            if rendered < 0 or accepted < 0 or accepted > rendered:
                raise HybridRoutingError("invalid_attempt_seconds")
            if status == "accepted" and accepted <= 0:
                raise HybridRoutingError("accepted_attempt_requires_accepted_seconds")
            if cost > _decimal(attempt["quoted_cost"]) and _decimal(attempt["quoted_cost"]) > 0:
                raise HybridRoutingError("actual_cost_exceeds_quote")
            if attempt["requires_spend_approval"]:
                approval = conn.execute(
                    "SELECT * FROM football_brief.hybrid_spend_approvals WHERE id=%s AND decision='approved'",
                    (attempt["spend_approval_id"],),
                ).fetchone()
                if not approval:
                    raise HybridRoutingError("explicit_spend_approval_required")
                total = _decimal(
                    conn.execute(
                        """SELECT COALESCE(sum(actual_cost),0) AS value
                           FROM football_brief.hybrid_route_attempts child
                           JOIN football_brief.hybrid_route_scenes scene ON scene.id=child.route_scene_id
                           WHERE scene.route_plan_id=%s AND child.id<>%s""",
                        (attempt["route_plan_id"], attempt_id),
                    ).fetchone()["value"]
                )
                if total + cost > _decimal(approval["approved_ceiling"]):
                    raise HybridRoutingError("actual_cost_exceeds_approved_ceiling")
            completed = conn.execute(
                """UPDATE football_brief.hybrid_route_attempts
                   SET status=%s,actual_cost=%s,rendered_seconds=%s,accepted_seconds=%s,
                       failure_code=%s,evidence=%s::jsonb,completed_at=now()
                   WHERE id=%s RETURNING *""",
                (status, cost, rendered, accepted, failure_code, _json(evidence or {}), attempt_id),
            ).fetchone()
            next_candidate = None
            if status == "accepted":
                conn.execute(
                    "UPDATE football_brief.hybrid_route_scenes SET status='accepted' WHERE id=%s",
                    (attempt["route_scene_id"],),
                )
                event_type = "scene_accepted"
            else:
                next_candidate = conn.execute(
                    """SELECT * FROM football_brief.hybrid_route_candidates
                       WHERE route_scene_id=%s AND eligible=true AND rank>%s
                       ORDER BY rank LIMIT 1""",
                    (attempt["route_scene_id"], attempt["rank"]),
                ).fetchone()
                if next_candidate:
                    next_status = "approval_required" if next_candidate["requires_spend_approval"] else "planned"
                    conn.execute(
                        """UPDATE football_brief.hybrid_route_scenes
                           SET selected_candidate_id=%s,render_class=%s,status=%s
                           WHERE id=%s""",
                        (
                            next_candidate["id"],
                            next_candidate["route_class"],
                            next_status,
                            attempt["route_scene_id"],
                        ),
                    )
                    event_type = "fallback_advanced"
                else:
                    conn.execute(
                        "UPDATE football_brief.hybrid_route_scenes SET status='blocked' WHERE id=%s",
                        (attempt["route_scene_id"],),
                    )
                    event_type = "attempt_completed"
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,route_scene_id,event_type,actor,details)
                   VALUES (%s,%s,%s,%s,%s::jsonb)""",
                (
                    attempt["route_plan_id"],
                    attempt["route_scene_id"],
                    event_type,
                    actor,
                    _json(
                        {
                            "attempt_id": str(attempt_id),
                            "status": status,
                            "failure_code": failure_code,
                            "next_candidate_id": str(next_candidate["id"]) if next_candidate else None,
                        }
                    ),
                ),
            )
            self._refresh_plan_status(conn, UUID(str(attempt["route_plan_id"])))
            return {
                "ok": True,
                "kind": "hybrid_route_attempt_completed",
                "idempotent": False,
                "attempt": _plain(dict(completed)),
                "next_candidate": _plain(dict(next_candidate)) if next_candidate else None,
            }

    def _package_context(self, conn, package_id: UUID, *, for_update: bool = False):
        lock = "FOR UPDATE OF package_row,item" if for_update else ""
        row = conn.execute(
            f"""SELECT package_row.id AS package_id,package_row.status AS package_status,
                       package_row.package_sha256,package_row.package,
                       item.id AS campaign_item_id,item.state AS item_state,
                       item.portfolio_content_id,version.campaign_id,campaign.brand_id
                FROM football_brief.pre_generation_packages package_row
                JOIN football_brief.production_campaign_items item
                  ON item.id=package_row.campaign_item_id
                JOIN football_brief.production_campaign_versions version
                  ON version.id=item.campaign_version_id
                JOIN football_brief.production_campaigns campaign
                  ON campaign.id=version.campaign_id
                WHERE package_row.id=%s {lock}""",
            (package_id,),
        ).fetchone()
        if not row:
            raise HybridRoutingError("pre_generation_package_not_found")
        if not row["portfolio_content_id"]:
            raise HybridRoutingError("package_portfolio_content_missing")
        return row

    def _ensure_policy(self, conn, *, brand_id: UUID, actor: str):
        policy = conn.execute(
            """SELECT * FROM football_brief.hybrid_routing_policies
               WHERE brand_id=%s AND status='active' FOR UPDATE""",
            (brand_id,),
        ).fetchone()
        if policy:
            return policy
        history = conn.execute(
            """SELECT * FROM football_brief.hybrid_routing_policies
               WHERE brand_id=%s ORDER BY version DESC LIMIT 1 FOR UPDATE""",
            (brand_id,),
        ).fetchone()
        version = int(history["version"]) + 1 if history else 1
        parent = history["id"] if history else None
        return conn.execute(
            """INSERT INTO football_brief.hybrid_routing_policies
               (brand_id,version,parent_policy_id,status,maximum_content_cost,
                maximum_scene_cost,created_by,activated_by,activated_at)
               VALUES (%s,%s,%s,'active',0,0,%s,%s,now()) RETURNING *""",
            (brand_id, version, parent, actor, actor),
        ).fetchone()

    def _active_budget_policy(self, conn, *, portfolio_content_id: UUID):
        return conn.execute(
            """SELECT policy.*
               FROM football_brief.portfolio_content content
               JOIN football_brief.monthly_content_plans plan ON plan.id=content.plan_id
               JOIN football_brief.production_budget_policies policy
                 ON policy.brand_id=plan.brand_id AND policy.month_start=plan.month_start
               WHERE content.id=%s AND policy.status='active'
               ORDER BY policy.version DESC LIMIT 1""",
            (portfolio_content_id,),
        ).fetchone()

    def _build_edl(self, package: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
        scene_plan = dict(package.get("scene_plan") or {})
        source_shots = _as_list(scene_plan.get("shots"))
        if not source_shots:
            source_shots = _as_list(scene_plan.get("timeline"))
        if not source_shots:
            source_shots = _as_list(package.get("scenes"))
        if not source_shots:
            raise HybridRoutingError("package_scene_plan_empty")
        target = _decimal(
            (package.get("content_family") or {}).get("target_duration_seconds")
            or scene_plan.get("exact_target_duration_seconds")
        )
        if target <= 0:
            raise HybridRoutingError("package_target_duration_missing")
        ordered = sorted(
            [dict(row) for row in source_shots],
            key=lambda row: (
                int(row.get("position") or row.get("sequence") or 0),
                str(row.get("shot_id") or row.get("scene_key") or ""),
            ),
        )
        cursor = Decimal("0")
        edl: list[dict[str, Any]] = []
        for index, row in enumerate(ordered, start=1):
            duration = _decimal(row.get("duration_seconds") or row.get("target_duration_seconds"))
            if duration <= 0:
                raise HybridRoutingError(
                    "invalid_scene_duration",
                    details={"scene": row.get("scene_key"), "duration": float(duration)},
                )
            supplied_start = row.get("start_seconds")
            supplied_end = row.get("end_seconds")
            if supplied_start is not None and abs(_decimal(supplied_start) - cursor) > Decimal("0.001"):
                raise HybridRoutingError(
                    "non_contiguous_scene_timeline",
                    details={"sequence": index, "expected_start": float(cursor)},
                )
            start = cursor
            end = start + duration
            if supplied_end is not None and abs(_decimal(supplied_end) - end) > Decimal("0.001"):
                raise HybridRoutingError(
                    "scene_end_mismatch",
                    details={"sequence": index, "expected_end": float(end)},
                )
            edl.append(
                {
                    "shot_id": str(row.get("shot_id") or f"S{index:03d}"),
                    "scene_key": str(row.get("scene_key") or row.get("shot_id") or f"scene-{index}"),
                    "sequence": index,
                    "start_seconds": start,
                    "end_seconds": end,
                    "duration_seconds": duration,
                    "prompt": str(row.get("prompt") or row.get("visual_brief") or "").strip(),
                    "negative_prompt": str(row.get("negative_prompt") or "").strip(),
                    "narration_text": str(row.get("narration_text") or "").strip(),
                    "continuity_bindings": dict(row.get("continuity_bindings") or {}),
                    "preferred_take_count": int(row.get("preferred_take_count") or 1),
                    "minimum_take_count": int(row.get("minimum_take_count") or 1),
                }
            )
            cursor = end
        delta = target - cursor
        corrected = False
        tolerance = max(Decimal("2"), target * Decimal("0.05"))
        if abs(delta) > Decimal("0.001"):
            if abs(delta) > tolerance:
                raise HybridRoutingError(
                    "package_duration_mismatch",
                    details={
                        "target_seconds": float(target),
                        "planned_seconds": float(cursor),
                        "delta_seconds": float(delta),
                    },
                )
            last = edl[-1]
            new_duration = _decimal(last["duration_seconds"]) + delta
            if new_duration < Decimal("1"):
                raise HybridRoutingError("package_duration_correction_invalid")
            last["duration_seconds"] = new_duration
            last["end_seconds"] = _decimal(last["start_seconds"]) + new_duration
            corrected = True
        if abs(_decimal(edl[-1]["end_seconds"]) - target) > Decimal("0.001"):
            raise HybridRoutingError("exact_edl_reconciliation_failed")
        return edl, corrected

    def _routing_resources(self, conn, *, brand_id: UUID, package: dict[str, Any]) -> dict[str, Any]:
        templates = conn.execute(
            """SELECT template.*,
                      EXISTS(
                        SELECT 1 FROM football_brief.asset_storage_locations location
                        WHERE location.asset_id=template.asset_id AND location.status='available'
                      ) AS asset_available
               FROM football_brief.hybrid_production_templates template
               WHERE template.status='active'
                 AND (template.brand_id IS NULL OR template.brand_id=%s)
               ORDER BY template.quality_rating DESC,template.template_key""",
            (brand_id,),
        ).fetchall()
        measurements = conn.execute(
            """SELECT * FROM football_brief.hybrid_renderer_measurements
               WHERE status='active' ORDER BY observed_at DESC,measurement_key"""
        ).fetchall()
        workflows = conn.execute(
            """SELECT workflow.*,entry.quality_rating,entry.health_status,
                      entry.expected_latency_seconds,entry.pricing,entry.pricing_currency,
                      entry.commercial_use_allowed
               FROM football_brief.local_video_workflows workflow
               LEFT JOIN football_brief.renderer_catalogue_entries entry
                 ON entry.id=workflow.renderer_catalogue_entry_id
               WHERE workflow.status='active'
               ORDER BY workflow.provider_key,workflow.workflow_key"""
        ).fetchall()
        renderers = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE status='active' AND commercial_use_allowed=true
                 AND health_status<>'unavailable' AND provider_key<>'simulated'
               ORDER BY quality_rating DESC,provider_key,model_key"""
        ).fetchall()
        return {
            "templates": [dict(row) for row in templates],
            "measurements": [dict(row) for row in measurements],
            "workflows": [dict(row) for row in workflows],
            "renderers": [dict(row) for row in renderers],
            "format": str(
                (package.get("content_family") or {}).get("format_name")
                or (package.get("content_family") or {}).get("primary_platform")
                or "master_video"
            ),
        }

    def _candidate_specs(
        self,
        *,
        scene: dict[str, Any],
        package: dict[str, Any],
        policy: dict[str, Any],
        policy_order: list[str],
        weights: dict[str, float],
        quality_floor: float,
        deadline: datetime,
        budget: dict[str, Any] | None,
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        territory = str((package.get("campaign") or {}).get("territory") or "global")
        duration = _decimal(scene["duration_seconds"])
        measurement_rows = resources["measurements"]

        for template in resources["templates"]:
            if template["category"] != "reusable_asset" or not template["asset_id"]:
                continue
            if not template["asset_available"] or not self._template_matches(template, scene):
                continue
            measurement = self._matching_measurement(
                measurement_rows,
                route_class="reuse_asset",
                template_id=template["id"],
            )
            candidates.append(
                self._score_candidate(
                    route_class="reuse_asset",
                    identity_key=f"template:{template['id']}",
                    policy_order=policy_order,
                    weights=weights,
                    quality_floor=quality_floor,
                    duration=duration,
                    deadline=deadline,
                    maximum_scene_cost=_decimal(policy["maximum_scene_cost"]),
                    budget=budget,
                    territory=territory,
                    template_id=template["id"],
                    measurement=measurement,
                    defaults={
                        "quality": float(template["quality_rating"]),
                        "acceptance": 0.99,
                        "cost_per_accepted_second": Decimal("0"),
                        "eta": 5,
                        "continuity_risk": 1,
                        "hardware_available": True,
                    },
                )
            )

        deterministic_measurement = self._matching_measurement(
            measurement_rows,
            route_class="deterministic_composition",
        )
        candidates.append(
            self._score_candidate(
                route_class="deterministic_composition",
                identity_key="builtin:deterministic-composition-v1",
                policy_order=policy_order,
                weights=weights,
                quality_floor=quality_floor,
                duration=duration,
                deadline=deadline,
                maximum_scene_cost=_decimal(policy["maximum_scene_cost"]),
                budget=budget,
                territory=territory,
                measurement=deterministic_measurement,
                defaults={
                    "quality": 88,
                    "acceptance": 0.98,
                    "cost_per_accepted_second": Decimal("0"),
                    "eta": max(30, int(duration * 3)),
                    "continuity_risk": 6,
                    "hardware_available": True,
                },
            )
        )

        for workflow in resources["workflows"]:
            if duration < _decimal(workflow["min_duration_seconds"]) or duration > _decimal(workflow["max_duration_seconds"]):
                continue
            measurement = self._matching_measurement(
                measurement_rows,
                route_class="local_generation",
                local_video_workflow_id=workflow["id"],
            )
            candidates.append(
                self._score_candidate(
                    route_class="local_generation",
                    identity_key=f"local-workflow:{workflow['id']}",
                    policy_order=policy_order,
                    weights=weights,
                    quality_floor=quality_floor,
                    duration=duration,
                    deadline=deadline,
                    maximum_scene_cost=_decimal(policy["maximum_scene_cost"]),
                    budget=budget,
                    territory=territory,
                    local_video_workflow_id=workflow["id"],
                    measurement=measurement,
                    defaults={
                        "quality": float(workflow.get("quality_rating") or 82),
                        "acceptance": 0.78,
                        "cost_per_accepted_second": Decimal("0"),
                        "eta": _eta_seconds(dict(workflow.get("expected_latency_seconds") or {}), 900),
                        "continuity_risk": 20,
                        "hardware_available": workflow.get("health_status") != "unavailable",
                    },
                )
            )

        for renderer in resources["renderers"]:
            if duration < _decimal(renderer["min_duration_seconds"]) or duration > _decimal(renderer["max_duration_seconds"]):
                continue
            route_class = self._renderer_route_class(renderer, measurement_rows)
            measurement = self._matching_measurement(
                measurement_rows,
                route_class=route_class,
                renderer_catalogue_entry_id=renderer["id"],
            )
            pricing = dict(renderer.get("pricing") or {})
            per_second = _pricing_per_second(pricing)
            if pricing.get("flat_cost") is not None and not any(
                pricing.get(key) is not None
                for key in ("cost_per_accepted_second", "cost_per_second", "per_second", "unit_cost_per_second", "per_minute")
            ):
                per_second = per_second / max(Decimal("1"), duration)
            candidates.append(
                self._score_candidate(
                    route_class=route_class,
                    identity_key=f"renderer:{renderer['id']}",
                    policy_order=policy_order,
                    weights=weights,
                    quality_floor=quality_floor,
                    duration=duration,
                    deadline=deadline,
                    maximum_scene_cost=_decimal(policy["maximum_scene_cost"]),
                    budget=budget,
                    territory=territory,
                    renderer_catalogue_entry_id=renderer["id"],
                    measurement=measurement,
                    defaults={
                        "quality": float(renderer["quality_rating"]),
                        "acceptance": 0.72,
                        "cost_per_accepted_second": per_second,
                        "eta": _eta_seconds(dict(renderer.get("expected_latency_seconds") or {}), 1200),
                        "continuity_risk": 25 if route_class == "cloud_portable" else 30,
                        "hardware_available": renderer["health_status"] != "unavailable",
                    },
                )
            )

        manual_measurement = self._matching_measurement(
            measurement_rows,
            route_class="manual_edit",
        )
        candidates.append(
            self._score_candidate(
                route_class="manual_edit",
                identity_key="builtin:manual-edit-v1",
                policy_order=policy_order,
                weights=weights,
                quality_floor=quality_floor,
                duration=duration,
                deadline=deadline,
                maximum_scene_cost=_decimal(policy["maximum_scene_cost"]),
                budget=budget,
                territory=territory,
                measurement=manual_measurement,
                defaults={
                    "quality": 100,
                    "acceptance": 1,
                    "cost_per_accepted_second": Decimal("0"),
                    "eta": 86400,
                    "continuity_risk": 0,
                    "hardware_available": True,
                },
            )
        )
        unique: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            current = unique.get(candidate["identity_key"])
            if current is None or candidate["score"] > current["score"]:
                unique[candidate["identity_key"]] = candidate
        return list(unique.values())

    def _score_candidate(
        self,
        *,
        route_class: str,
        identity_key: str,
        policy_order: list[str],
        weights: dict[str, float],
        quality_floor: float,
        duration: Decimal,
        deadline: datetime,
        maximum_scene_cost: Decimal,
        budget: dict[str, Any] | None,
        territory: str,
        measurement: dict[str, Any] | None,
        defaults: dict[str, Any],
        renderer_catalogue_entry_id: UUID | None = None,
        local_video_workflow_id: UUID | None = None,
        template_id: UUID | None = None,
    ) -> dict[str, Any]:
        quality = float(measurement["quality_score"] if measurement else defaults["quality"])
        acceptance = float(measurement["acceptance_rate"] if measurement else defaults["acceptance"])
        cost_per_accepted_second = _decimal(
            measurement["cost_per_accepted_second"] if measurement else defaults["cost_per_accepted_second"]
        )
        estimated_cost = (cost_per_accepted_second * duration).quantize(Decimal("0.000001"))
        eta = int(measurement["queue_eta_p50_seconds"] if measurement else defaults["eta"])
        continuity_risk = float(
            measurement["continuity_risk"] if measurement else defaults["continuity_risk"]
        )
        hardware = bool(
            measurement["hardware_available"] if measurement else defaults["hardware_available"]
        )
        territories = list(measurement["supported_territories"] or []) if measurement else ["global"]
        rejection: list[str] = []
        if quality < quality_floor:
            rejection.append("quality_floor_not_met")
        if not hardware:
            rejection.append("hardware_or_provider_unavailable")
        if territories and "global" not in territories and territory not in territories:
            rejection.append("territory_not_supported")
        paid = route_class in PAID_ROUTE_CLASSES or estimated_cost > 0
        if paid and budget is None:
            rejection.append("active_budget_policy_required")
        if paid and maximum_scene_cost <= 0:
            rejection.append("scene_cost_ceiling_zero")
        elif paid and estimated_cost > maximum_scene_cost:
            rejection.append("scene_cost_ceiling_exceeded")
        seconds_remaining = max(1, int((deadline - datetime.now(timezone.utc)).total_seconds()))
        if eta > seconds_remaining:
            rejection.append("deadline_eta_miss")
        route_index = policy_order.index(route_class)
        route_priority = 100 if len(policy_order) == 1 else 100 - (route_index * 100 / (len(policy_order) - 1))
        cost_score = 100.0
        if estimated_cost > 0:
            cost_score = 0 if maximum_scene_cost <= 0 else _clamp(
                100 - (float(estimated_cost / maximum_scene_cost) * 100)
            )
        eta_score = _clamp(100 - (eta / seconds_remaining * 100))
        components = {
            "route_priority": route_priority,
            "quality": quality,
            "acceptance": acceptance * 100,
            "cost": cost_score,
            "eta": eta_score,
            "continuity": 100 - continuity_risk,
        }
        score = round(sum(components[key] * weights[key] for key in weights), 4)
        return {
            "identity_key": identity_key,
            "route_class": route_class,
            "renderer_catalogue_entry_id": renderer_catalogue_entry_id,
            "local_video_workflow_id": local_video_workflow_id,
            "template_id": template_id,
            "measurement_id": measurement["id"] if measurement else None,
            "eligible": not rejection,
            "requires_spend_approval": paid,
            "score": score,
            "estimated_cost": estimated_cost,
            "expected_eta_seconds": eta,
            "acceptance_rate": acceptance,
            "quality_score": quality,
            "continuity_risk": continuity_risk,
            "rejection_reasons": rejection,
            "scoring_evidence": {
                "router_version": ROUTER_VERSION,
                "components": components,
                "weights": weights,
                "quality_floor": quality_floor,
                "cost_per_accepted_second": float(cost_per_accepted_second),
                "measurement_id": str(measurement["id"]) if measurement else None,
                "measurement_sample_size": int(measurement["sample_size"]) if measurement else 0,
                "measured": measurement is not None,
                "paid_request_submitted": False,
            },
        }

    def _matching_measurement(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        route_class: str,
        renderer_catalogue_entry_id: UUID | None = None,
        local_video_workflow_id: UUID | None = None,
        template_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        for row in rows:
            if row["route_class"] != route_class:
                continue
            if renderer_catalogue_entry_id and row["renderer_catalogue_entry_id"] != renderer_catalogue_entry_id:
                continue
            if local_video_workflow_id and row["local_video_workflow_id"] != local_video_workflow_id:
                continue
            if template_id and row["template_id"] != template_id:
                continue
            if not any((renderer_catalogue_entry_id, local_video_workflow_id, template_id)) and any(
                (row["renderer_catalogue_entry_id"], row["local_video_workflow_id"], row["template_id"])
            ):
                continue
            return row
        return None

    def _renderer_route_class(self, renderer: dict[str, Any], measurements: list[dict[str, Any]]) -> str:
        for row in measurements:
            if row["renderer_catalogue_entry_id"] == renderer["id"]:
                return str(row["route_class"])
        capabilities = dict(renderer.get("capabilities") or {})
        if capabilities.get("portable_workflow") or capabilities.get("cloud_portable"):
            return "cloud_portable"
        pricing = _pricing_per_second(dict(renderer.get("pricing") or {}))
        if float(renderer["quality_rating"]) >= 92 or pricing >= Decimal("0.20"):
            return "premium_hero"
        return "premium_low_cost"

    def _template_matches(self, template: dict[str, Any], scene: dict[str, Any]) -> bool:
        specification = dict(template.get("specification") or {})
        if specification.get("all_scenes") is True:
            return True
        shot_ids = {str(value) for value in _as_list(specification.get("shot_ids"))}
        scene_keys = {str(value) for value in _as_list(specification.get("scene_keys"))}
        return scene["shot_id"] in shot_ids or scene["scene_key"] in scene_keys

    def _weights(self, configured: dict[str, Any]) -> dict[str, float]:
        defaults = {
            "route_priority": 0.30,
            "quality": 0.25,
            "acceptance": 0.15,
            "cost": 0.15,
            "eta": 0.10,
            "continuity": 0.05,
        }
        values = {key: max(0.0, float(configured.get(key, value))) for key, value in defaults.items()}
        total = sum(values.values()) or 1
        return {key: value / total for key, value in values.items()}

    def _is_hero(self, scene: dict[str, Any], scene_count: int) -> bool:
        return int(scene["sequence"]) in {1, 2, scene_count} or int(scene.get("preferred_take_count") or 1) > 1

    def _continuity_group(self, scene: dict[str, Any], package: dict[str, Any]) -> str:
        binding = dict(scene.get("continuity_bindings") or {})
        persistent = binding.get("content_family_id") or (package.get("content_family") or {}).get("content_family_id")
        return str(persistent or "package-continuity")[:240]

    def _keyframe_requirements(self, scene: dict[str, Any]) -> dict[str, Any]:
        prompt = str(scene.get("prompt") or "").lower()
        return {
            "start_frame_required": scene["sequence"] == 1 or "start frame" in prompt,
            "end_frame_required": "end frame" in prompt,
            "continuity_reference_required": bool(scene.get("continuity_bindings")),
            "editorial_text_only": True,
        }

    def _motion_intensity(self, scene: dict[str, Any]) -> float:
        prompt = str(scene.get("prompt") or "").lower()
        high = ("fast", "dynamic", "rapid", "action", "sweep", "tracking")
        low = ("still", "restrained", "slow", "subtle", "locked")
        value = 55.0
        if any(word in prompt for word in high):
            value += 25
        if any(word in prompt for word in low):
            value -= 25
        return _clamp(value)

    def _scene_rationale(self, scene: dict[str, Any]) -> str:
        selected = next(
            (item for item in scene["candidates"] if item["identity_key"] == scene["selected_identity"]),
            None,
        )
        if selected is None:
            return "No route met the quality, policy, territory, deadline and cost constraints."
        return (
            f"Selected {selected['route_class']} as the earliest eligible route in the versioned "
            f"policy order with score {selected['score']:.4f}; {len(scene['candidates']) - 1} "
            "documented alternatives remain in the fallback chain."
        )

    def _monthly_committed(self, conn, *, policy: dict[str, Any], exclude_plan_id: UUID) -> Decimal:
        legacy = _decimal(
            conn.execute(
                """SELECT COALESCE(sum(
                         CASE WHEN reservation.status='reserved'
                              THEN reservation.reserved_amount ELSE reservation.actual_amount END
                       ),0) AS value
                   FROM football_brief.production_spend_reservations reservation
                   JOIN football_brief.portfolio_content content ON content.id=reservation.portfolio_content_id
                   JOIN football_brief.monthly_content_plans plan ON plan.id=content.plan_id
                   WHERE plan.brand_id=%s AND plan.month_start=%s
                     AND reservation.status IN ('reserved','reconciled')""",
                (policy["brand_id"], policy["month_start"]),
            ).fetchone()["value"]
        )
        hybrid = _decimal(
            conn.execute(
                """SELECT COALESCE(sum(approval.approved_ceiling),0) AS value
                   FROM football_brief.hybrid_spend_approvals approval
                   JOIN football_brief.hybrid_route_plans route_plan ON route_plan.id=approval.route_plan_id
                   WHERE approval.budget_policy_id=%s AND approval.decision='approved'
                     AND route_plan.id<>%s""",
                (policy["id"], exclude_plan_id),
            ).fetchone()["value"]
        )
        return legacy + hybrid

    def _refresh_plan_status(self, conn, plan_id: UUID) -> None:
        counts = conn.execute(
            """SELECT count(*)::int AS total,
                      count(*) FILTER (WHERE status='accepted')::int AS accepted,
                      count(*) FILTER (WHERE status='blocked')::int AS blocked,
                      count(*) FILTER (WHERE status='approval_required')::int AS approval_required,
                      count(*) FILTER (WHERE status IN ('queued','running'))::int AS executing
               FROM football_brief.hybrid_route_scenes WHERE route_plan_id=%s""",
            (plan_id,),
        ).fetchone()
        if counts["total"] and counts["accepted"] == counts["total"]:
            status = "completed"
            completed_sql = ",completed_at=now()"
        elif counts["blocked"]:
            status = "blocked"
            completed_sql = ""
        elif counts["approval_required"]:
            status = "approval_required"
            completed_sql = ""
        elif counts["executing"]:
            status = "executing"
            completed_sql = ""
        else:
            status = "ready"
            completed_sql = ""
        conn.execute(
            f"UPDATE football_brief.hybrid_route_plans SET status=%s{completed_sql} WHERE id=%s",
            (status, plan_id),
        )
        if status == "completed":
            conn.execute(
                """INSERT INTO football_brief.hybrid_route_events
                   (route_plan_id,event_type,actor,details)
                   VALUES (%s,'plan_completed','system',%s::jsonb)""",
                (plan_id, _json({"completed": True})),
            )

    def _detail_locked(self, conn, plan_id: UUID) -> dict[str, Any]:
        plan = conn.execute(
            "SELECT * FROM football_brief.hybrid_route_plans WHERE id=%s",
            (plan_id,),
        ).fetchone()
        if not plan:
            raise HybridRoutingError("hybrid_route_plan_not_found")
        scenes = conn.execute(
            """SELECT * FROM football_brief.hybrid_route_scenes
               WHERE route_plan_id=%s ORDER BY sequence""",
            (plan_id,),
        ).fetchall()
        candidates = conn.execute(
            """SELECT candidate.*
               FROM football_brief.hybrid_route_candidates candidate
               JOIN football_brief.hybrid_route_scenes scene ON scene.id=candidate.route_scene_id
               WHERE scene.route_plan_id=%s ORDER BY scene.sequence,candidate.rank""",
            (plan_id,),
        ).fetchall()
        attempts = conn.execute(
            """SELECT attempt.*
               FROM football_brief.hybrid_route_attempts attempt
               JOIN football_brief.hybrid_route_scenes scene ON scene.id=attempt.route_scene_id
               WHERE scene.route_plan_id=%s ORDER BY scene.sequence,attempt.attempt_number""",
            (plan_id,),
        ).fetchall()
        approval = conn.execute(
            "SELECT * FROM football_brief.hybrid_spend_approvals WHERE route_plan_id=%s",
            (plan_id,),
        ).fetchone()
        events = conn.execute(
            """SELECT * FROM football_brief.hybrid_route_events
               WHERE route_plan_id=%s ORDER BY created_at,id""",
            (plan_id,),
        ).fetchall()
        by_scene: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            by_scene.setdefault(str(candidate["route_scene_id"]), []).append(_plain(dict(candidate)))
        scene_payload = []
        for scene in scenes:
            payload = _plain(dict(scene))
            payload["candidates"] = by_scene.get(str(scene["id"]), [])
            scene_payload.append(payload)
        return {
            "ok": True,
            "kind": "hybrid_route_plan",
            "plan": _plain(dict(plan)),
            "scenes": scene_payload,
            "attempts": [_plain(dict(row)) for row in attempts],
            "spend_approval": _plain(dict(approval)) if approval else None,
            "events": [_plain(dict(row)) for row in events],
            "automatic_paid_execution": False,
            "public_publishing": False,
        }

    def _require_operator(self, conn, actor: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if not row:
            raise HybridRoutingError("operator_inactive_or_missing")


__all__ = [
    "HybridRoutingError",
    "HybridRoutingService",
    "PAID_ROUTE_CLASSES",
    "ROUTE_CLASSES",
    "ROUTER_VERSION",
]
