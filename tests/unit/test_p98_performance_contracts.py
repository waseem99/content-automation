from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.performance import (
    ExperimentCreateRequest,
    ExperimentVariantRequest,
    PerformanceAnalyticsService,
    PerformanceImportRequest,
    PerformanceObservationInput,
    RecommendationRequest,
    WinnerCriteria,
)


ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "migrations/0026_portfolio_content_engine.sql"
FOUNDATION = ROOT / "migrations/0077_performance_analytics_foundation.sql"
INTEGRITY = ROOT / "migrations/0078_performance_analytics_integrity.sql"
FLEXIBILITY = ROOT / "migrations/0079_performance_delivery_variant_flexibility.sql"
RUNTIME = ROOT / "src/operator_api/performance_runtime.py"


def observation(**overrides):
    payload = {
        "source_observation_id": "metric-row-001",
        "delivery_request_id": "00000000-0000-4000-8000-000000000001",
        "observed_at": datetime.now(timezone.utc),
        "window_seconds": 3600,
        "post_status": "published",
        "views": 1000,
        "normalized_views": 900,
        "retention_rate": "0.55",
        "completion_rate": "0.41",
        "rewatch_rate": "0.08",
        "engagement_count": 120,
        "engagement_rate": "0.12",
        "shares": 15,
        "follower_growth": 7,
        "revenue_amount": "5.50",
        "revenue_currency": "USD",
        "revenue_usd": "5.50",
    }
    payload.update(overrides)
    return PerformanceObservationInput(**payload)


def test_legacy_analytics_table_is_preserved() -> None:
    legacy = LEGACY.read_text(encoding="utf-8")
    foundation = FOUNDATION.read_text(encoding="utf-8")
    integrity = INTEGRITY.read_text(encoding="utf-8")
    assert "CREATE TABLE football_brief.performance_observations" in legacy
    assert "CREATE TABLE football_brief.performance_delivery_observations" in foundation
    assert "BEFORE INSERT ON football_brief.performance_delivery_observations" in integrity
    assert "CREATE TABLE football_brief.performance_observations" not in foundation


def test_import_models_reject_bad_normalization_timezones_and_secrets() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        observation(views=100, normalized_views=101)
    with pytest.raises(ValidationError, match="explicit time zone"):
        observation(observed_at=datetime.now())
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="secret material"):
        PerformanceImportRequest(
            brand_id="00000000-0000-4000-8000-000000000002",
            platform="instagram",
            source_system="manual-export",
            source_account_ref="token=committed-secret",
            idempotency_key="p98-import-contract",
            observed_from=now - timedelta(minutes=5),
            observed_to=now + timedelta(minutes=5),
            observations=(observation(observed_at=now),),
        )


def test_experiment_allows_delivery_variants_of_same_release() -> None:
    release_id = "00000000-0000-4000-8000-000000000010"
    request = ExperimentCreateRequest(
        brand_id="00000000-0000-4000-8000-000000000011",
        experiment_key="hook-copy-test",
        display_name="Hook Copy Test",
        hypothesis="A direct factual hook will improve normalized views.",
        winner_criteria=WinnerCriteria(
            metric="normalized_views",
            direction="maximize",
            minimum_relative_difference="0.10",
        ),
        minimum_observation_count=2,
        minimum_views_per_variant=1000,
        variants=(
            ExperimentVariantRequest(
                variant_key="a",
                label="Direct hook",
                final_release_id=release_id,
                delivery_request_id="00000000-0000-4000-8000-000000000012",
                declared_changes={"title": "direct"},
            ),
            ExperimentVariantRequest(
                variant_key="b",
                label="Curiosity hook",
                final_release_id=release_id,
                delivery_request_id="00000000-0000-4000-8000-000000000013",
                declared_changes={"title": "curiosity"},
            ),
        ),
    )
    assert request.variants[0].final_release_id == request.variants[1].final_release_id
    flexibility = FLEXIBILITY.read_text(encoding="utf-8")
    assert "FROM pg_constraint" in flexibility
    assert "performance_experiment_variants_experiment_id_final_release%" in flexibility


def test_recommendations_cannot_authorize_automatic_actions() -> None:
    with pytest.raises(ValidationError, match="automatic approval"):
        RecommendationRequest(
            brand_id="00000000-0000-4000-8000-000000000021",
            recommendation_key="unsafe-recommendation",
            recommendation="Auto-publish this winning format without review.",
            cited_observation_ids=("00000000-0000-4000-8000-000000000022",),
            metric_citations=({"metric": "normalized_views", "value": 2000},),
            confidence="high",
        )


def test_api_is_advisory_and_has_no_production_or_delivery_mutations() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    assert '@app.post("/performance/imports")' in source
    assert '@app.post("/performance/experiments/{experiment_id}/evaluate")' in source
    assert '@app.post("/performance/recommendations")' in source
    lowered = source.lower()
    assert '"/performance/publish' not in lowered
    assert '"/performance/deliver' not in lowered
    assert '"/performance/approve' not in lowered
    assert PerformanceAnalyticsService is not None
