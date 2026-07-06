from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class ReviewTargetType(StrEnum):
    RIGHTS_GATE = "rights_gate"
    SCRIPT = "script"
    RENDER_MANIFEST = "render_manifest"
    QUALITY_REPORT = "quality_report"
    STAGE = "stage"
    WORKFLOW = "workflow"
    COMPLIANCE = "compliance"


class ReviewRequestStatus(StrEnum):
    OPEN = "open"
    DECIDED = "decided"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ReviewDecision(StrEnum):
    PASS = "pass"
    PASS_WITH_DISCLOSURE = "pass_with_disclosure"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    BLOCK = "block"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ReviewRequestCreate(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID | None = None
    target_type: ReviewTargetType
    target_id: UUID | None = None
    review_type: str = Field(min_length=1)
    assigned_to: str | None = None
    requested_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    prevent_self_approval: bool = True
    required_checklist: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewRequest(ReviewRequestCreate):
    id: UUID
    status: ReviewRequestStatus
    created_at: datetime
    decided_at: datetime | None = None


class ReviewDecisionCreate(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID | None = None
    review_request_id: UUID | None = None
    review_type: str = Field(min_length=1)
    decision: ReviewDecision
    reviewer: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    checklist: dict[str, Any] = Field(min_length=1)
    target_type: ReviewTargetType | None = None
    target_id: UUID | None = None
    supersedes_review_id: UUID | None = None
    disclosure_texts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanReview(ReviewDecisionCreate):
    id: UUID
    created_at: datetime


class ReviewHistory(FrozenRecord):
    workflow_run_id: UUID
    decisions: tuple[HumanReview, ...]
