from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping
from uuid import UUID

from src.application.performance.models import (
    ExperimentCreateRequest,
    ExperimentEvaluateRequest,
    PerformanceImportRequest,
    RecommendationRequest,
    ResultStatus,
    WinnerDirection,
    WinnerMetric,
)
from src.infrastructure.database.connection import Database


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class PerformanceAnalyticsError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(code)


class PerformanceAnalyticsService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def import_batch(
        self,
        request: PerformanceImportRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        source_document = request.model_dump(mode="json")
        source_digest = _hash(source_document)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"performance-import:{request.idempotency_key}",),
            )
            existing = conn.execute(
                "SELECT * FROM football_brief.performance_import_batches WHERE idempotency_key=%s FOR SHARE",
                (request.idempotency_key,),
            ).fetchone()
            if existing:
                if existing["source_digest"] != source_digest:
                    raise PerformanceAnalyticsError(
                        "performance_import_idempotency_conflict",
                        details={"batch_id": str(existing["id"])},
                    )
                batch_id = existing["id"]
                reused = True
            else:
                batch = conn.execute(
                    """INSERT INTO football_brief.performance_import_batches
                       (brand_id,platform,source_system,source_account_ref,idempotency_key,
                        source_digest,observed_from,observed_to,row_count,metadata,imported_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                       RETURNING *""",
                    (
                        request.brand_id,
                        request.platform,
                        request.source_system,
                        request.source_account_ref,
                        request.idempotency_key,
                        source_digest,
                        request.observed_from,
                        request.observed_to,
                        len(request.observations),
                        _json(request.metadata),
                        actor,
                    ),
                ).fetchone()
                batch_id = batch["id"]
                reused = False

            if not reused:
                for item in request.observations:
                    context = self._delivery_context(conn, item.delivery_request_id)
                    if str(context["brand_id"]) != str(request.brand_id):
                        raise PerformanceAnalyticsError(
                            "performance_observation_brand_mismatch",
                            details={"delivery_request_id": str(item.delivery_request_id)},
                        )
                    if str(context["platform"]).lower() != request.platform:
                        raise PerformanceAnalyticsError(
                            "performance_observation_platform_mismatch",
                            details={
                                "delivery_request_id": str(item.delivery_request_id),
                                "delivery_platform": context["platform"],
                                "batch_platform": request.platform,
                            },
                        )
                    creative_snapshot = self._creative_snapshot(conn, context)
                    production_cost = self._production_cost(conn, context)
                    metric_source_snapshot = {
                        "source_system": request.source_system,
                        "source_account_ref": request.source_account_ref,
                        "source_digest": source_digest,
                        "source_observation_id": item.source_observation_id,
                        "source_metrics": item.source_metrics,
                    }
                    fingerprint_document = {
                        "source_system": request.source_system,
                        "source_account_ref": request.source_account_ref,
                        "source_observation_id": item.source_observation_id,
                        "delivery_request_id": str(item.delivery_request_id),
                        "observed_at": item.observed_at.isoformat(),
                        "window_seconds": item.window_seconds,
                        "post_status": item.post_status.value,
                        "metrics": item.model_dump(mode="json", exclude={"source_metrics"}),
                    }
                    fingerprint = _hash(fingerprint_document)
                    duplicate = conn.execute(
                        "SELECT id FROM football_brief.performance_delivery_observations WHERE observation_fingerprint=%s",
                        (fingerprint,),
                    ).fetchone()
                    if duplicate:
                        raise PerformanceAnalyticsError(
                            "performance_observation_already_imported",
                            details={
                                "observation_id": str(duplicate["id"]),
                                "source_observation_id": item.source_observation_id,
                            },
                        )
                    conn.execute(
                        """INSERT INTO football_brief.performance_delivery_observations
                           (import_batch_id,source_observation_id,observation_fingerprint,
                            delivery_request_id,final_release_id,brand_id,portfolio_content_id,
                            content_version,platform,post_reference,post_status,observed_at,
                            window_seconds,views,normalized_views,retention_rate,completion_rate,
                            rewatch_rate,engagement_count,engagement_rate,shares,follower_growth,
                            revenue_amount,revenue_currency,revenue_usd,production_cost_usd,
                            creative_snapshot,metric_source_snapshot,imported_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                   %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)""",
                        (
                            batch_id,
                            item.source_observation_id,
                            fingerprint,
                            item.delivery_request_id,
                            context["final_release_id"],
                            context["brand_id"],
                            context["portfolio_content_id"],
                            context["content_version"],
                            context["platform"],
                            context["platform_reference"],
                            item.post_status.value,
                            item.observed_at,
                            item.window_seconds,
                            item.views,
                            item.normalized_views,
                            item.retention_rate,
                            item.completion_rate,
                            item.rewatch_rate,
                            item.engagement_count,
                            item.engagement_rate,
                            item.shares,
                            item.follower_growth,
                            item.revenue_amount,
                            item.revenue_currency,
                            item.revenue_usd,
                            production_cost,
                            _json(creative_snapshot),
                            _json(metric_source_snapshot),
                            actor,
                        ),
                    )
        result = self.import_detail(batch_id=batch_id)
        result["reused"] = reused
        return result

    def import_detail(self, *, batch_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            batch = conn.execute(
                "SELECT * FROM football_brief.performance_import_batches WHERE id=%s",
                (batch_id,),
            ).fetchone()
            if not batch:
                raise PerformanceAnalyticsError("performance_import_batch_not_found")
            observations = conn.execute(
                """SELECT * FROM football_brief.performance_delivery_observation_economics
                   WHERE import_batch_id=%s ORDER BY observed_at,source_observation_id""",
                (batch_id,),
            ).fetchall()
        return {
            "ok": True,
            "batch": dict(batch),
            "observations": [dict(row) for row in observations],
        }

    def list_observations(
        self,
        *,
        brand_ids: Iterable[UUID] | None = None,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        latest_per_delivery: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise PerformanceAnalyticsError("invalid_performance_list_limit")
        brand_list = list(brand_ids) if brand_ids is not None else None
        with self.database.connection() as conn:
            if latest_per_delivery:
                rows = conn.execute(
                    """SELECT * FROM (
                           SELECT DISTINCT ON (delivery_request_id) *
                           FROM football_brief.performance_delivery_observation_economics
                           WHERE (%s::uuid[] IS NULL OR brand_id=ANY(%s::uuid[]))
                             AND (%s::timestamptz IS NULL OR observed_at>=%s)
                             AND (%s::timestamptz IS NULL OR observed_at<=%s)
                           ORDER BY delivery_request_id,observed_at DESC,id DESC
                       ) latest
                       ORDER BY observed_at DESC,id DESC LIMIT %s""",
                    (
                        brand_list,
                        brand_list,
                        observed_from,
                        observed_from,
                        observed_to,
                        observed_to,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM football_brief.performance_delivery_observation_economics
                       WHERE (%s::uuid[] IS NULL OR brand_id=ANY(%s::uuid[]))
                         AND (%s::timestamptz IS NULL OR observed_at>=%s)
                         AND (%s::timestamptz IS NULL OR observed_at<=%s)
                       ORDER BY observed_at DESC,id DESC LIMIT %s""",
                    (
                        brand_list,
                        brand_list,
                        observed_from,
                        observed_from,
                        observed_to,
                        observed_to,
                        limit,
                    ),
                ).fetchall()
        return [dict(row) for row in rows]

    def dashboard(
        self,
        *,
        brand_id: UUID,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        minimum_items: int = 3,
        minimum_normalized_views: int = 1000,
    ) -> dict[str, Any]:
        if minimum_items < 1 or minimum_normalized_views < 0:
            raise PerformanceAnalyticsError("invalid_dashboard_sufficiency_threshold")
        rows = self.list_observations(
            brand_ids=(brand_id,),
            observed_from=observed_from,
            observed_to=observed_to,
            latest_per_delivery=True,
            limit=1000,
        )
        total_views = sum(int(row["views"]) for row in rows)
        normalized_views = sum(int(row["normalized_views"]) for row in rows)
        production_cost = sum((_decimal(row["production_cost_usd"]) for row in rows), Decimal("0"))
        revenue = sum((_decimal(row["revenue_usd"]) for row in rows), Decimal("0"))
        data_status = (
            "meaningful"
            if len(rows) >= minimum_items and normalized_views >= minimum_normalized_views
            else "insufficient_data"
        )
        return {
            "ok": True,
            "brand_id": str(brand_id),
            "data_status": data_status,
            "sufficiency": {
                "observed_items": len(rows),
                "minimum_items": minimum_items,
                "normalized_views": normalized_views,
                "minimum_normalized_views": minimum_normalized_views,
            },
            "metrics": {
                "items": len(rows),
                "views": total_views,
                "normalized_views": normalized_views,
                "retention_rate": self._weighted_rate(rows, "retention_rate"),
                "completion_rate": self._weighted_rate(rows, "completion_rate"),
                "rewatch_rate": self._weighted_rate(rows, "rewatch_rate"),
                "engagement_count": sum(int(row["engagement_count"]) for row in rows),
                "engagement_rate": self._weighted_rate(rows, "engagement_rate"),
                "shares": sum(int(row["shares"]) for row in rows),
                "follower_growth": sum(int(row["follower_growth"]) for row in rows),
                "revenue_usd": revenue,
                "production_cost_usd": production_cost,
                "cost_per_item_usd": (
                    production_cost / Decimal(len(rows)) if rows else None
                ),
                "cost_per_thousand_views_usd": (
                    production_cost * Decimal(1000) / Decimal(normalized_views)
                    if normalized_views
                    else None
                ),
                "revenue_per_thousand_views_usd": (
                    revenue * Decimal(1000) / Decimal(normalized_views)
                    if normalized_views
                    else None
                ),
                "contribution_after_production_cost_usd": revenue - production_cost,
            },
            "creative_breakdown": self._creative_breakdown(rows),
            "observations": rows,
        }

    def create_experiment(
        self,
        request: ExperimentCreateRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"performance-experiment:{request.brand_id}:{request.experiment_key}",),
            )
            existing = conn.execute(
                """SELECT id,status FROM football_brief.performance_experiments
                   WHERE brand_id=%s AND experiment_key=%s ORDER BY version DESC LIMIT 1""",
                (request.brand_id, request.experiment_key),
            ).fetchone()
            if existing:
                raise PerformanceAnalyticsError(
                    "performance_experiment_key_exists",
                    details={"experiment_id": str(existing["id"]), "status": existing["status"]},
                )
            experiment = conn.execute(
                """INSERT INTO football_brief.performance_experiments
                   (brand_id,experiment_key,display_name,version,status,hypothesis,
                    winner_criteria,minimum_observation_count,minimum_views_per_variant,
                    significance_threshold,created_by)
                   VALUES (%s,%s,%s,1,'draft',%s,%s::jsonb,%s,%s,%s,%s) RETURNING *""",
                (
                    request.brand_id,
                    request.experiment_key,
                    request.display_name,
                    request.hypothesis,
                    _json(request.winner_criteria.model_dump(mode="json")),
                    request.minimum_observation_count,
                    request.minimum_views_per_variant,
                    request.significance_threshold,
                    actor,
                ),
            ).fetchone()
            for variant in request.variants:
                conn.execute(
                    """INSERT INTO football_brief.performance_experiment_variants
                       (experiment_id,variant_key,label,final_release_id,delivery_request_id,
                        declared_changes,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                    (
                        experiment["id"],
                        variant.variant_key,
                        variant.label,
                        variant.final_release_id,
                        variant.delivery_request_id,
                        _json(variant.declared_changes),
                        actor,
                    ),
                )
        return self.experiment_detail(experiment_id=experiment["id"])

    def activate_experiment(self, *, experiment_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            updated = conn.execute(
                """UPDATE football_brief.performance_experiments
                   SET status='active',activated_at=now()
                   WHERE id=%s AND status='draft' RETURNING *""",
                (experiment_id,),
            ).fetchone()
            if not updated:
                raise PerformanceAnalyticsError("performance_experiment_not_draft")
        return self.experiment_detail(experiment_id=experiment_id)

    def evaluate_experiment(
        self,
        *,
        experiment_id: UUID,
        request: ExperimentEvaluateRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            experiment = conn.execute(
                "SELECT * FROM football_brief.performance_experiments WHERE id=%s FOR UPDATE",
                (experiment_id,),
            ).fetchone()
            if not experiment:
                raise PerformanceAnalyticsError("performance_experiment_not_found")
            if experiment["status"] not in {"active", "completed"}:
                raise PerformanceAnalyticsError(
                    "performance_experiment_not_active",
                    details={"status": experiment["status"]},
                )
            variants = conn.execute(
                """SELECT * FROM football_brief.performance_experiment_variants
                   WHERE experiment_id=%s ORDER BY variant_key""",
                (experiment_id,),
            ).fetchall()
            criteria = dict(experiment["winner_criteria"])
            metric = WinnerMetric(criteria["metric"])
            direction = WinnerDirection(criteria["direction"])
            minimum_effect = _decimal(criteria.get("minimum_relative_difference", "0.05"))
            summaries: list[dict[str, Any]] = []
            evidence_ids: list[UUID] = []
            sufficient = True
            for variant in variants:
                observations = conn.execute(
                    """SELECT * FROM football_brief.performance_delivery_observation_economics
                       WHERE delivery_request_id=%s ORDER BY observed_at,id""",
                    (variant["delivery_request_id"],),
                ).fetchall()
                evidence_ids.extend(row["id"] for row in observations)
                latest = observations[-1] if observations else None
                observation_count = len(observations)
                latest_views = int(latest["normalized_views"]) if latest else 0
                variant_sufficient = (
                    observation_count >= int(experiment["minimum_observation_count"])
                    and latest_views >= int(experiment["minimum_views_per_variant"])
                )
                sufficient = sufficient and variant_sufficient
                value = self._metric_value(latest, metric) if latest else None
                summaries.append(
                    {
                        "variant_id": str(variant["id"]),
                        "variant_key": variant["variant_key"],
                        "delivery_request_id": str(variant["delivery_request_id"]),
                        "observation_count": observation_count,
                        "latest_normalized_views": latest_views,
                        "sufficient": variant_sufficient,
                        "metric": metric.value,
                        "metric_value": value,
                        "latest_observation_id": str(latest["id"]) if latest else None,
                    }
                )

            winner_variant_id = None
            effect = None
            if not evidence_ids or not sufficient:
                result_status = ResultStatus.INSUFFICIENT_DATA
            else:
                ranked = sorted(
                    summaries,
                    key=lambda item: _decimal(item["metric_value"]),
                    reverse=direction == WinnerDirection.MAXIMIZE,
                )
                best = ranked[0]
                second = ranked[1]
                best_value = _decimal(best["metric_value"])
                second_value = _decimal(second["metric_value"])
                denominator = abs(second_value)
                if direction == WinnerDirection.MAXIMIZE:
                    raw_effect = best_value - second_value
                else:
                    raw_effect = second_value - best_value
                effect = raw_effect / denominator if denominator else (
                    Decimal("1") if raw_effect > 0 else Decimal("0")
                )
                if effect >= minimum_effect:
                    result_status = ResultStatus.MEANINGFUL_RESULT
                    winner_variant_id = UUID(best["variant_id"])
                else:
                    result_status = ResultStatus.NO_WINNER

            sequence = int(
                conn.execute(
                    """SELECT COALESCE(max(evaluation_sequence),0)+1 AS sequence
                       FROM football_brief.performance_experiment_results
                       WHERE experiment_id=%s""",
                    (experiment_id,),
                ).fetchone()["sequence"]
            )
            metric_summary = {
                "variants": summaries,
                "minimum_relative_difference": str(minimum_effect),
                "observed_relative_difference": str(effect) if effect is not None else None,
                "significance_threshold": str(experiment["significance_threshold"]),
                "statistical_significance_test_applied": False,
                "interpretation": (
                    "Declared sample, view, and relative-effect thresholds passed."
                    if result_status == ResultStatus.MEANINGFUL_RESULT
                    else "The evidence did not meet every declared threshold."
                ),
            }
            result = conn.execute(
                """INSERT INTO football_brief.performance_experiment_results
                   (experiment_id,evaluation_sequence,result_status,winner_variant_id,
                    evaluated_observation_ids,criteria_snapshot,metric_summary,rationale,evaluated_by)
                   VALUES (%s,%s,%s,%s,%s::uuid[],%s::jsonb,%s::jsonb,%s,%s) RETURNING *""",
                (
                    experiment_id,
                    sequence,
                    result_status.value,
                    winner_variant_id,
                    evidence_ids,
                    _json(criteria),
                    _json(metric_summary),
                    request.rationale,
                    actor,
                ),
            ).fetchone()
            if result_status != ResultStatus.INSUFFICIENT_DATA and experiment["status"] == "active":
                conn.execute(
                    """UPDATE football_brief.performance_experiments
                       SET status='completed',completed_at=now() WHERE id=%s""",
                    (experiment_id,),
                )
        detail = self.experiment_detail(experiment_id=experiment_id)
        detail["evaluation"] = dict(result)
        return detail

    def create_recommendation(
        self,
        request: RecommendationRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            recommendation = conn.execute(
                """INSERT INTO football_brief.performance_recommendations
                   (brand_id,experiment_result_id,recommendation_key,recommendation,
                    cited_observation_ids,metric_citations,confidence,advisory_only,created_by)
                   VALUES (%s,%s,%s,%s,%s::uuid[],%s::jsonb,%s,true,%s) RETURNING *""",
                (
                    request.brand_id,
                    request.experiment_result_id,
                    request.recommendation_key,
                    request.recommendation,
                    list(request.cited_observation_ids),
                    _json(list(request.metric_citations)),
                    request.confidence.value,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "recommendation": dict(recommendation)}

    def experiment_detail(self, *, experiment_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            experiment = conn.execute(
                "SELECT * FROM football_brief.performance_experiments WHERE id=%s",
                (experiment_id,),
            ).fetchone()
            if not experiment:
                raise PerformanceAnalyticsError("performance_experiment_not_found")
            variants = conn.execute(
                """SELECT * FROM football_brief.performance_experiment_variants
                   WHERE experiment_id=%s ORDER BY variant_key""",
                (experiment_id,),
            ).fetchall()
            results = conn.execute(
                """SELECT * FROM football_brief.performance_experiment_results
                   WHERE experiment_id=%s ORDER BY evaluation_sequence""",
                (experiment_id,),
            ).fetchall()
        return {
            "ok": True,
            "experiment": dict(experiment),
            "variants": [dict(row) for row in variants],
            "results": [dict(row) for row in results],
        }

    def list_experiments(
        self,
        *,
        brand_ids: Iterable[UUID] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise PerformanceAnalyticsError("invalid_experiment_list_limit")
        brand_list = list(brand_ids) if brand_ids is not None else None
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT pe.*,
                          (SELECT count(*) FROM football_brief.performance_experiment_variants pev
                           WHERE pev.experiment_id=pe.id) AS variant_count,
                          (SELECT count(*) FROM football_brief.performance_experiment_results per
                           WHERE per.experiment_id=pe.id) AS evaluation_count
                   FROM football_brief.performance_experiments pe
                   WHERE (%s::uuid[] IS NULL OR pe.brand_id=ANY(%s::uuid[]))
                   ORDER BY pe.created_at DESC,pe.version DESC LIMIT %s""",
                (brand_list, brand_list, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]):
            raise PerformanceAnalyticsError("operator_inactive_or_missing")

    @staticmethod
    def _delivery_context(conn: Any, delivery_request_id: UUID) -> Mapping[str, Any]:
        row = conn.execute(
            """SELECT pdr.id AS delivery_request_id,pdr.final_release_id,pdr.platform_reference,
                      pdr.status AS delivery_status,pdr.metadata AS delivery_metadata,
                      pdt.platform,pdt.target_key,
                      fr.portfolio_content_id,fr.content_version,fr.routing_plan_id,
                      fr.total_cost_usd,fr.release_manifest,fr.manifest_hash,
                      agj.provider AS assembly_provider,agj.model_id AS assembly_model_id,
                      pc.title,pc.concept,pc.concept_fingerprint,pc.semantic_key,pc.format,
                      pc.metadata AS content_metadata,pc.brand_profile_id,pc.narration_preset_id,
                      mp.brand_id,mp.strategy AS plan_strategy,
                      sv.id AS script_version_id,sv.hook_text,sv.target_duration_seconds,
                      sv.format AS script_format,
                      ap.narration_preset_id AS audio_narration_preset_id,
                      amv.duration_seconds AS audio_duration_seconds,
                      vp.id AS visual_project_id,vp.visual_preset_id,vp.provider AS visual_provider,
                      vp.model_id AS visual_model_id,
                      bvp.preset_key AS visual_preset_key,bvp.version AS visual_preset_version,
                      bvp.palette AS visual_palette,bvp.subject_rules AS visual_subject_rules,
                      bvp.environment_rules AS visual_environment_rules,
                      bvp.camera_rules AS visual_camera_rules,
                      bvp.lighting_rules AS visual_lighting_rules,
                      bvp.framing_rules AS visual_framing_rules
               FROM football_brief.platform_delivery_requests pdr
               JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
               JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
               JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               LEFT JOIN football_brief.generation_jobs agj ON agj.id=fr.assembly_job_id
               JOIN football_brief.audio_mix_versions amv ON amv.id=fr.audio_mix_version_id
               JOIN football_brief.audio_productions ap ON ap.id=amv.audio_production_id
               JOIN football_brief.script_versions sv ON sv.id=ap.script_version_id
               LEFT JOIN football_brief.visual_projects vp
                 ON vp.portfolio_content_id=fr.portfolio_content_id
                AND vp.content_version=fr.content_version
                AND vp.status='approved'
               LEFT JOIN football_brief.brand_visual_presets bvp ON bvp.id=vp.visual_preset_id
               WHERE pdr.id=%s""",
            (delivery_request_id,),
        ).fetchone()
        if not row:
            raise PerformanceAnalyticsError("performance_delivery_not_found")
        if row["delivery_status"] != "succeeded" or not row["platform_reference"]:
            raise PerformanceAnalyticsError(
                "performance_delivery_not_succeeded",
                details={"status": row["delivery_status"]},
            )
        return row

    @staticmethod
    def _production_cost(conn: Any, context: Mapping[str, Any]) -> Decimal:
        routed = Decimal("0")
        if context["routing_plan_id"]:
            routed = _decimal(
                conn.execute(
                    """SELECT COALESCE(sum(actual_amount),0) AS actual
                       FROM football_brief.production_spend_reservations
                       WHERE routing_plan_id=%s AND status='reconciled'""",
                    (context["routing_plan_id"],),
                ).fetchone()["actual"]
            )
        return (_decimal(context["total_cost_usd"]) + routed).quantize(Decimal("0.000001"))

    @staticmethod
    def _creative_snapshot(conn: Any, context: Mapping[str, Any]) -> dict[str, Any]:
        content_metadata = dict(context["content_metadata"] or {})
        plan_strategy = dict(context["plan_strategy"] or {})
        pillar_sources = (
            (content_metadata.get("content_pillar"), "content_metadata.content_pillar"),
            (content_metadata.get("pillar"), "content_metadata.pillar"),
            (plan_strategy.get("content_pillar"), "plan_strategy.content_pillar"),
            (plan_strategy.get("pillar"), "plan_strategy.pillar"),
        )
        pillar, pillar_source = next(
            ((value, source) for value, source in pillar_sources if value),
            ("unclassified", "not_declared"),
        )
        renderers: list[dict[str, Any]] = []
        if context["routing_plan_id"]:
            rows = conn.execute(
                """SELECT vs.sequence,sri.route,rce.provider_key,rce.model_key,
                          gj.provider AS job_provider,gj.model_id AS job_model_id
                   FROM football_brief.shot_routing_items sri
                   JOIN football_brief.visual_shots vs ON vs.id=sri.visual_shot_id
                   LEFT JOIN football_brief.renderer_preflight_records rpr
                     ON rpr.id=sri.renderer_preflight_id
                   LEFT JOIN football_brief.renderer_catalogue_entries rce
                     ON rce.id=rpr.renderer_catalogue_entry_id
                   LEFT JOIN football_brief.production_spend_reservations psr
                     ON psr.routing_item_id=sri.id
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=psr.generation_job_id
                   WHERE sri.routing_plan_id=%s ORDER BY vs.sequence,sri.id""",
                (context["routing_plan_id"],),
            ).fetchall()
            renderers = [
                {
                    "sequence": int(row["sequence"]),
                    "route": row["route"],
                    "provider": row["job_provider"] or row["provider_key"] or context["visual_provider"],
                    "model_id": row["job_model_id"] or row["model_key"] or context["visual_model_id"],
                }
                for row in rows
            ]
        if not renderers and context["visual_provider"]:
            renderers.append(
                {
                    "sequence": 1,
                    "route": "local_visual_project",
                    "provider": context["visual_provider"],
                    "model_id": context["visual_model_id"],
                }
            )
        renderers.append(
            {
                "sequence": len(renderers) + 1,
                "route": "final_assembly",
                "provider": context["assembly_provider"],
                "model_id": context["assembly_model_id"],
            }
        )
        return {
            "concept": {
                "text": context["concept"],
                "fingerprint": context["concept_fingerprint"],
                "semantic_key": context["semantic_key"],
            },
            "pillar": pillar,
            "pillar_source": pillar_source,
            "hook": context["hook_text"],
            "duration_seconds": str(
                context["audio_duration_seconds"] or context["target_duration_seconds"]
            ),
            "narration_preset_id": str(
                context["audio_narration_preset_id"] or context["narration_preset_id"]
            ),
            "brand_profile_id": str(context["brand_profile_id"]),
            "visual_style": {
                "visual_project_id": str(context["visual_project_id"]) if context["visual_project_id"] else None,
                "visual_preset_id": str(context["visual_preset_id"]) if context["visual_preset_id"] else None,
                "preset_key": context["visual_preset_key"],
                "version": context["visual_preset_version"],
                "palette": context["visual_palette"],
                "subject_rules": context["visual_subject_rules"],
                "environment_rules": context["visual_environment_rules"],
                "camera_rules": context["visual_camera_rules"],
                "lighting_rules": context["visual_lighting_rules"],
                "framing_rules": context["visual_framing_rules"],
            },
            "renderers": renderers,
            "format": context["script_format"] or context["format"],
            "release_id": str(context["final_release_id"]),
            "delivery_request_id": str(context["delivery_request_id"]),
            "target_key": context["target_key"],
        }

    @staticmethod
    def _weighted_rate(rows: list[Mapping[str, Any]], key: str) -> Decimal | None:
        weighted = Decimal("0")
        weight = 0
        for row in rows:
            if row[key] is None:
                continue
            views = int(row["normalized_views"])
            if views <= 0:
                continue
            weighted += _decimal(row[key]) * Decimal(views)
            weight += views
        return weighted / Decimal(weight) if weight else None

    @staticmethod
    def _creative_breakdown(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        dimensions = {
            "pillar": lambda snapshot: snapshot.get("pillar"),
            "format": lambda snapshot: snapshot.get("format"),
            "narration_preset_id": lambda snapshot: snapshot.get("narration_preset_id"),
            "visual_preset_id": lambda snapshot: (snapshot.get("visual_style") or {}).get("visual_preset_id"),
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for name, resolver in dimensions.items():
            groups: dict[str, dict[str, Any]] = {}
            for row in rows:
                snapshot = dict(row["creative_snapshot"] or {})
                value = resolver(snapshot)
                key = str(value) if value is not None else "unclassified"
                group = groups.setdefault(
                    key,
                    {
                        "value": value,
                        "items": 0,
                        "normalized_views": 0,
                        "revenue_usd": Decimal("0"),
                        "production_cost_usd": Decimal("0"),
                    },
                )
                group["items"] += 1
                group["normalized_views"] += int(row["normalized_views"])
                group["revenue_usd"] += _decimal(row["revenue_usd"])
                group["production_cost_usd"] += _decimal(row["production_cost_usd"])
            result[name] = list(groups.values())
        return result

    @staticmethod
    def _metric_value(row: Mapping[str, Any], metric: WinnerMetric) -> Decimal:
        if metric == WinnerMetric.COST_PER_ITEM_USD:
            return _decimal(row["production_cost_usd"])
        return _decimal(row[metric.value])
