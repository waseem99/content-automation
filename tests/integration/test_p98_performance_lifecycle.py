from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from src.application.performance import (
    ExperimentCreateRequest,
    ExperimentEvaluateRequest,
    ExperimentVariantRequest,
    PerformanceAnalyticsError,
    PerformanceAnalyticsService,
    PerformanceImportRequest,
    PerformanceObservationInput,
    RecommendationRequest,
    WinnerCriteria,
)
from tests.integration.p98_performance_support import p89_database, p98_ready


pytestmark = pytest.mark.integration


def metric_row(
    ready,
    *,
    delivery_key: str,
    source_id: str,
    observed_at: datetime,
    window_seconds: int,
    views: int,
    normalized_views: int,
    retention: str,
    completion: str,
    rewatch: str,
    engagement_rate: str,
    shares: int,
    followers: int,
    revenue: str,
) -> PerformanceObservationInput:
    delivery = ready[delivery_key]
    return PerformanceObservationInput(
        source_observation_id=source_id,
        delivery_request_id=delivery["id"],
        observed_at=observed_at,
        window_seconds=window_seconds,
        post_status="published",
        views=views,
        normalized_views=normalized_views,
        retention_rate=retention,
        completion_rate=completion,
        rewatch_rate=rewatch,
        engagement_count=int(normalized_views * float(engagement_rate)),
        engagement_rate=engagement_rate,
        shares=shares,
        follower_growth=followers,
        revenue_amount=revenue,
        revenue_currency="USD",
        revenue_usd=revenue,
        source_metrics={"simulated": True, "window_seconds": window_seconds},
    )


def import_request(
    ready,
    *,
    key: str,
    observed_at: datetime,
    suffix: str,
    a_views: int,
    b_views: int,
) -> PerformanceImportRequest:
    return PerformanceImportRequest(
        brand_id=ready["brand_one"],
        platform="instagram",
        source_system="simulated-platform-export",
        source_account_ref="account:p98-analytics-target",
        idempotency_key=key,
        observed_from=observed_at - timedelta(minutes=5),
        observed_to=observed_at + timedelta(minutes=5),
        observations=(
            metric_row(
                ready,
                delivery_key="delivery_a",
                source_id=f"variant-a-{suffix}",
                observed_at=observed_at,
                window_seconds=3600 if suffix == "early" else 86400,
                views=a_views,
                normalized_views=int(a_views * 0.9),
                retention="0.62",
                completion="0.48",
                rewatch="0.11",
                engagement_rate="0.14",
                shares=32 if suffix == "late" else 6,
                followers=18 if suffix == "late" else 3,
                revenue="9.00" if suffix == "late" else "1.50",
            ),
            metric_row(
                ready,
                delivery_key="delivery_b",
                source_id=f"variant-b-{suffix}",
                observed_at=observed_at,
                window_seconds=3600 if suffix == "early" else 86400,
                views=b_views,
                normalized_views=int(b_views * 0.9),
                retention="0.51",
                completion="0.36",
                rewatch="0.06",
                engagement_rate="0.09",
                shares=14 if suffix == "late" else 4,
                followers=7 if suffix == "late" else 2,
                revenue="4.00" if suffix == "late" else "1.00",
            ),
        ),
        metadata={"phase": "P98", "window": suffix},
    )


def experiment_request(ready, *, key: str, minimum_effect: str = "0.10") -> ExperimentCreateRequest:
    return ExperimentCreateRequest(
        brand_id=ready["brand_one"],
        experiment_key=key,
        display_name="Controlled Hook Copy Experiment",
        hypothesis="The direct factual hook will improve normalized views over curiosity copy.",
        winner_criteria=WinnerCriteria(
            metric="normalized_views",
            direction="maximize",
            minimum_relative_difference=minimum_effect,
        ),
        minimum_observation_count=2,
        minimum_views_per_variant=1000,
        significance_threshold="0.95",
        variants=(
            ExperimentVariantRequest(
                variant_key="a",
                label="Direct factual hook",
                final_release_id=ready["release_id"],
                delivery_request_id=ready["delivery_a"]["id"],
                declared_changes={
                    "title": "Variant A: direct factual hook",
                    "privacy": "private",
                },
            ),
            ExperimentVariantRequest(
                variant_key="b",
                label="Curiosity-led hook",
                final_release_id=ready["release_id"],
                delivery_request_id=ready["delivery_b"]["id"],
                declared_changes={
                    "title": "Variant B: curiosity-led hook",
                    "privacy": "unlisted",
                },
            ),
        ),
    )


def test_idempotent_import_dashboard_and_append_only_economics(
    p89_database,
    p98_ready,
) -> None:
    service = PerformanceAnalyticsService(p89_database)
    observed_at = datetime.now(timezone.utc)
    request = import_request(
        p98_ready,
        key="p98-early-import",
        observed_at=observed_at,
        suffix="early",
        a_views=500,
        b_views=400,
    )
    imported = service.import_batch(request, actor=p98_ready["admin"])
    reused = service.import_batch(request, actor=p98_ready["admin"])
    assert imported["reused"] is False
    assert reused["reused"] is True
    assert reused["batch"]["id"] == imported["batch"]["id"]
    assert len(imported["observations"]) == 2

    for row in imported["observations"]:
        snapshot = row["creative_snapshot"]
        assert snapshot["concept"]["text"]
        assert snapshot["hook"]
        assert snapshot["duration_seconds"]
        assert snapshot["narration_preset_id"]
        assert "visual_style" in snapshot
        assert snapshot["renderers"]
        assert snapshot["format"]
        assert snapshot["release_id"] == str(p98_ready["release_id"])
        assert row["post_reference"] in {
            p98_ready["delivery_a"]["platform_reference"],
            p98_ready["delivery_b"]["platform_reference"],
        }
        assert row["cost_per_item_usd"] == row["production_cost_usd"]

    changed = request.model_copy(
        update={
            "observations": (
                request.observations[0].model_copy(update={"views": 999}),
                request.observations[1],
            )
        }
    )
    with pytest.raises(PerformanceAnalyticsError, match="performance_import_idempotency_conflict"):
        service.import_batch(changed, actor=p98_ready["admin"])

    insufficient = service.dashboard(
        brand_id=p98_ready["brand_one"],
        minimum_items=3,
        minimum_normalized_views=1000,
    )
    assert insufficient["data_status"] == "insufficient_data"
    meaningful = service.dashboard(
        brand_id=p98_ready["brand_one"],
        minimum_items=2,
        minimum_normalized_views=500,
    )
    assert meaningful["data_status"] == "meaningful"
    assert meaningful["metrics"]["items"] == 2
    assert meaningful["metrics"]["normalized_views"] == 810
    assert meaningful["metrics"]["contribution_after_production_cost_usd"] == (
        meaningful["metrics"]["revenue_usd"] - meaningful["metrics"]["production_cost_usd"]
    )

    observation_id = imported["observations"][0]["id"]
    with pytest.raises(psycopg.Error, match="append-only"):
        with p89_database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.performance_delivery_observations
                   SET views=views+1 WHERE id=%s""",
                (observation_id,),
            )


def test_experiment_distinguishes_insufficient_meaningful_and_no_winner(
    p89_database,
    p98_ready,
) -> None:
    service = PerformanceAnalyticsService(p89_database)
    early_at = datetime.now(timezone.utc)
    early = service.import_batch(
        import_request(
            p98_ready,
            key="p98-experiment-early",
            observed_at=early_at,
            suffix="early",
            a_views=600,
            b_views=500,
        ),
        actor=p98_ready["admin"],
    )
    experiment = service.create_experiment(
        experiment_request(p98_ready, key="p98-hook-winner"),
        actor=p98_ready["admin"],
    )
    experiment_id = experiment["experiment"]["id"]
    service.activate_experiment(experiment_id=experiment_id, actor=p98_ready["admin"])
    insufficient = service.evaluate_experiment(
        experiment_id=experiment_id,
        request=ExperimentEvaluateRequest(
            rationale="One observation per variant is not enough to identify a winner."
        ),
        actor=p98_ready["reviewer"],
    )
    assert insufficient["evaluation"]["result_status"] == "insufficient_data"
    assert insufficient["experiment"]["status"] == "active"

    late = service.import_batch(
        import_request(
            p98_ready,
            key="p98-experiment-late",
            observed_at=early_at + timedelta(hours=24),
            suffix="late",
            a_views=3000,
            b_views=1500,
        ),
        actor=p98_ready["admin"],
    )
    meaningful = service.evaluate_experiment(
        experiment_id=experiment_id,
        request=ExperimentEvaluateRequest(
            rationale="Both variants meet the declared sample and view thresholds; A exceeds B materially."
        ),
        actor=p98_ready["reviewer"],
    )
    assert meaningful["evaluation"]["result_status"] == "meaningful_result"
    assert meaningful["experiment"]["status"] == "completed"
    winner = next(item for item in meaningful["variants"] if item["id"] == meaningful["evaluation"]["winner_variant_id"])
    assert winner["variant_key"] == "a"
    assert meaningful["evaluation"]["metric_summary"]["statistical_significance_test_applied"] is False

    evidence = [row["id"] for row in early["observations"] + late["observations"]]
    recommendation = service.create_recommendation(
        RecommendationRequest(
            brand_id=p98_ready["brand_one"],
            experiment_result_id=meaningful["evaluation"]["id"],
            recommendation_key="prefer-direct-factual-hook",
            recommendation=(
                "Prefer the direct factual hook in the next reviewed concept slate because it produced "
                "more normalized views under the declared controlled thresholds."
            ),
            cited_observation_ids=tuple(evidence),
            metric_citations=(
                {
                    "metric": "normalized_views",
                    "variant_a": 2700,
                    "variant_b": 1350,
                    "source": "P98 controlled experiment",
                },
            ),
            confidence="high",
        ),
        actor=p98_ready["reviewer"],
    )["recommendation"]
    assert recommendation["advisory_only"] is True
    assert recommendation["experiment_result_id"] == meaningful["evaluation"]["id"]

    with pytest.raises(psycopg.Error, match="append-only"):
        with p89_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.performance_recommendations SET confidence='low' WHERE id=%s",
                (recommendation["id"],),
            )

    no_winner_experiment = service.create_experiment(
        experiment_request(
            p98_ready,
            key="p98-hook-no-winner",
            minimum_effect="2.00",
        ),
        actor=p98_ready["admin"],
    )
    no_winner_id = no_winner_experiment["experiment"]["id"]
    service.activate_experiment(experiment_id=no_winner_id, actor=p98_ready["admin"])
    no_winner = service.evaluate_experiment(
        experiment_id=no_winner_id,
        request=ExperimentEvaluateRequest(
            rationale="The relative difference does not meet the deliberately strict winner threshold."
        ),
        actor=p98_ready["reviewer"],
    )
    assert no_winner["evaluation"]["result_status"] == "no_winner"
    assert no_winner["evaluation"]["winner_variant_id"] is None
