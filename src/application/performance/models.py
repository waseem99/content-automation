from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PostStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    DELETED = "deleted"
    PRIVATE = "private"
    UNLISTED = "unlisted"
    UNKNOWN = "unknown"


class WinnerMetric(StrEnum):
    NORMALIZED_VIEWS = "normalized_views"
    RETENTION_RATE = "retention_rate"
    COMPLETION_RATE = "completion_rate"
    REWATCH_RATE = "rewatch_rate"
    ENGAGEMENT_RATE = "engagement_rate"
    SHARES = "shares"
    FOLLOWER_GROWTH = "follower_growth"
    REVENUE_USD = "revenue_usd"
    COST_PER_ITEM_USD = "cost_per_item_usd"
    COST_PER_THOUSAND_VIEWS_USD = "cost_per_thousand_views_usd"
    REVENUE_PER_THOUSAND_VIEWS_USD = "revenue_per_thousand_views_usd"
    CONTRIBUTION_AFTER_PRODUCTION_COST_USD = "contribution_after_production_cost_usd"


class WinnerDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ResultStatus(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    MEANINGFUL_RESULT = "meaningful_result"
    NO_WINNER = "no_winner"


class RecommendationConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PerformanceObservationInput(BaseModel):
    source_observation_id: str = Field(min_length=1, max_length=500)
    delivery_request_id: UUID
    observed_at: datetime
    window_seconds: int = Field(ge=0, le=10 * 365 * 24 * 60 * 60)
    post_status: PostStatus
    views: int = Field(default=0, ge=0)
    normalized_views: int = Field(default=0, ge=0)
    retention_rate: Decimal | None = Field(default=None, ge=0, le=1)
    completion_rate: Decimal | None = Field(default=None, ge=0, le=1)
    rewatch_rate: Decimal | None = Field(default=None, ge=0, le=1)
    engagement_count: int = Field(default=0, ge=0)
    engagement_rate: Decimal | None = Field(default=None, ge=0, le=1)
    shares: int = Field(default=0, ge=0)
    follower_growth: int = 0
    revenue_amount: Decimal = Field(default=Decimal("0"), ge=0)
    revenue_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    revenue_usd: Decimal = Field(default=Decimal("0"), ge=0)
    source_metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_observation_id", mode="before")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_normalization(self) -> "PerformanceObservationInput":
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include an explicit time zone")
        if self.normalized_views > self.views:
            raise ValueError("normalized_views cannot exceed views")
        if self.views == 0 and any(
            value not in (None, Decimal("0"))
            for value in (
                self.retention_rate,
                self.completion_rate,
                self.rewatch_rate,
                self.engagement_rate,
            )
        ):
            raise ValueError("rate metrics require at least one source view")
        return self


class PerformanceImportRequest(BaseModel):
    brand_id: UUID
    platform: str = Field(min_length=2, max_length=80)
    source_system: str = Field(min_length=2, max_length=120)
    source_account_ref: str = Field(min_length=3, max_length=240)
    idempotency_key: str = Field(min_length=8, max_length=240)
    observed_from: datetime
    observed_to: datetime
    observations: tuple[PerformanceObservationInput, ...] = Field(min_length=1, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("platform", "source_system", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("source_account_ref", "idempotency_key", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_batch(self) -> "PerformanceImportRequest":
        for value, label in (
            (self.observed_from, "observed_from"),
            (self.observed_to, "observed_to"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must include an explicit time zone")
        if self.observed_to < self.observed_from:
            raise ValueError("observed_to must be on or after observed_from")
        identities = [item.source_observation_id for item in self.observations]
        if len(identities) != len(set(identities)):
            raise ValueError("source_observation_id values must be unique within a batch")
        if any(
            marker in self.source_account_ref.lower()
            for marker in ("password=", "secret=", "token=", "api_key=", "api-key=")
        ):
            raise ValueError("source_account_ref must not contain secret material")
        if any(
            item.observed_at < self.observed_from or item.observed_at > self.observed_to
            for item in self.observations
        ):
            raise ValueError("every observation must fall inside the declared batch window")
        return self


class WinnerCriteria(BaseModel):
    metric: WinnerMetric
    direction: WinnerDirection = WinnerDirection.MAXIMIZE
    minimum_relative_difference: Decimal = Field(default=Decimal("0.05"), ge=0, le=10)


class ExperimentVariantRequest(BaseModel):
    variant_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    label: str = Field(min_length=1, max_length=200)
    final_release_id: UUID
    delivery_request_id: UUID
    declared_changes: dict[str, Any]

    @field_validator("variant_key", mode="before")
    @classmethod
    def normalize_variant_key(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("label", mode="before")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def require_declared_change(self) -> "ExperimentVariantRequest":
        if not self.declared_changes:
            raise ValueError("declared_changes cannot be empty")
        return self


class ExperimentCreateRequest(BaseModel):
    brand_id: UUID
    experiment_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=3, max_length=200)
    hypothesis: str = Field(min_length=10, max_length=5000)
    winner_criteria: WinnerCriteria
    minimum_observation_count: int = Field(default=2, ge=1, le=1000)
    minimum_views_per_variant: int = Field(default=1000, ge=0)
    significance_threshold: Decimal = Field(default=Decimal("0.95"), gt=0, le=1)
    variants: tuple[ExperimentVariantRequest, ...] = Field(min_length=2, max_length=20)

    @field_validator("experiment_key", mode="before")
    @classmethod
    def normalize_experiment_key(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def unique_variants(self) -> "ExperimentCreateRequest":
        keys = [item.variant_key for item in self.variants]
        deliveries = [item.delivery_request_id for item in self.variants]
        if len(keys) != len(set(keys)):
            raise ValueError("variant_key values must be unique")
        if len(deliveries) != len(set(deliveries)):
            raise ValueError("each delivery request may appear only once")
        return self


class ExperimentEvaluateRequest(BaseModel):
    rationale: str = Field(min_length=3, max_length=5000)


class RecommendationRequest(BaseModel):
    brand_id: UUID
    experiment_result_id: UUID | None = None
    recommendation_key: str = Field(min_length=3, max_length=160)
    recommendation: str = Field(min_length=10, max_length=5000)
    cited_observation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1000)
    metric_citations: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=100)
    confidence: RecommendationConfidence

    @field_validator("recommendation_key", mode="before")
    @classmethod
    def normalize_recommendation_key(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_advisory_text(self) -> "RecommendationRequest":
        lowered = self.recommendation.lower()
        if any(
            phrase in lowered
            for phrase in (
                "auto approve",
                "auto-approve",
                "auto publish",
                "auto-publish",
                "auto deliver",
                "auto-deliver",
                "without review",
            )
        ):
            raise ValueError("recommendations cannot authorize automatic approval or delivery")
        if len(self.cited_observation_ids) != len(set(self.cited_observation_ids)):
            raise ValueError("cited_observation_ids must be unique")
        return self
