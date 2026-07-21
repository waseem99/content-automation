from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ConceptAdapterMode(StrEnum):
    LOCAL_MODEL = "local_model"
    DETERMINISTIC = "deterministic"


class CandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    DUPLICATE_BLOCKED = "duplicate_blocked"


class CandidateReviewAction(StrEnum):
    SHORTLIST = "shortlist"
    RESTORE = "restore"
    REJECT = "reject"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProductionRoute(StrEnum):
    LOCAL = "local"
    HYBRID = "hybrid"
    MANAGED = "managed"


class ConceptBatchRequest(BaseModel):
    brand_id: UUID
    month_start: date
    candidate_count: int = Field(default=30, ge=1, le=200)
    format_mix: dict[str, int] = Field(min_length=1)
    pillar_targets: dict[str, int] = Field(min_length=1)
    seed: int = Field(default=20260801, ge=0)
    adapter_mode: ConceptAdapterMode = ConceptAdapterMode.DETERMINISTIC
    local_model_id: str | None = Field(default=None, max_length=200)
    local_endpoint: str | None = Field(default=None, max_length=500)
    local_timeout_seconds: int = Field(default=20, ge=1, le=120)

    @field_validator("month_start")
    @classmethod
    def require_month_start(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("month_start must be the first day of a month")
        return value

    @field_validator("format_mix", "pillar_targets")
    @classmethod
    def normalize_targets(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, count in value.items():
            name = str(key).strip().lower().replace(" ", "_")
            if len(name) < 2:
                raise ValueError("distribution keys must contain at least two characters")
            if int(count) < 0:
                raise ValueError("distribution counts cannot be negative")
            if int(count) > 0:
                normalized[name] = int(count)
        if not normalized:
            raise ValueError("at least one positive distribution target is required")
        return normalized

    @model_validator(mode="after")
    def validate_totals_and_adapter(self) -> "ConceptBatchRequest":
        if sum(self.format_mix.values()) != self.candidate_count:
            raise ValueError("format_mix must sum to candidate_count")
        if sum(self.pillar_targets.values()) != self.candidate_count:
            raise ValueError("pillar_targets must sum to candidate_count")
        if self.adapter_mode == ConceptAdapterMode.LOCAL_MODEL:
            if not (self.local_model_id or "").strip():
                raise ValueError("local_model_id is required for local_model mode")
            if self.local_endpoint:
                endpoint = self.local_endpoint.strip().lower()
                if not endpoint.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
                    raise ValueError("local_endpoint must resolve to localhost")
        return self


class CandidateDraft(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    hook: str = Field(min_length=3, max_length=500)
    concept: str = Field(min_length=20, max_length=5000)
    format: str = Field(min_length=2, max_length=80)
    pillar: str = Field(min_length=2, max_length=120)
    rationale: str = Field(min_length=20, max_length=5000)
    source_requirements: list[str] = Field(default_factory=list, max_length=30)
    required_research: list[str] = Field(default_factory=list, max_length=30)
    factual_risk: RiskLevel
    production_complexity: RiskLevel
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    recommended_route: ProductionRoute = ProductionRoute.LOCAL
    generation_evidence: dict[str, Any] = Field(default_factory=dict)


class CandidateRevisionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    hook: str | None = Field(default=None, min_length=3, max_length=500)
    concept: str | None = Field(default=None, min_length=20, max_length=5000)
    format: str | None = Field(default=None, min_length=2, max_length=80)
    pillar: str | None = Field(default=None, min_length=2, max_length=120)
    rationale: str | None = Field(default=None, min_length=20, max_length=5000)
    source_requirements: list[str] | None = Field(default=None, max_length=30)
    required_research: list[str] | None = Field(default=None, max_length=30)
    factual_risk: RiskLevel | None = None
    production_complexity: RiskLevel | None = None
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    recommended_route: ProductionRoute | None = None
    revision_reason: str = Field(min_length=3, max_length=5000)

    @model_validator(mode="after")
    def require_change(self) -> "CandidateRevisionRequest":
        editable = self.model_dump(exclude={"revision_reason"}, exclude_none=True)
        if not editable:
            raise ValueError("at least one candidate field must change")
        return self


class CandidateReviewRequest(BaseModel):
    action: CandidateReviewAction
    rationale: str = Field(min_length=3, max_length=5000)


class SlateBuildRequest(BaseModel):
    batch_id: UUID
    selected_count: int = Field(ge=1, le=180)
    format_mix: dict[str, int] = Field(min_length=1)
    pillar_targets: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_totals(self) -> "SlateBuildRequest":
        if sum(self.format_mix.values()) != self.selected_count:
            raise ValueError("format_mix must sum to selected_count")
        if sum(self.pillar_targets.values()) != self.selected_count:
            raise ValueError("pillar_targets must sum to selected_count")
        return self


class SlateScheduleItem(BaseModel):
    candidate_id: UUID
    scheduled_for: date


class SlateApplyRequest(BaseModel):
    plan_id: UUID
    items: list[SlateScheduleItem] = Field(min_length=1, max_length=180)

    @model_validator(mode="after")
    def require_unique_candidates_and_dates(self) -> "SlateApplyRequest":
        candidate_ids = [item.candidate_id for item in self.items]
        dates = [item.scheduled_for for item in self.items]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate IDs must be unique")
        if len(set(dates)) != len(dates):
            raise ValueError("scheduled dates must be unique")
        return self
