"""Typed records used by the Phase 0/1 persistence foundation.

These models contain no SQL and can be used by services, CLI commands, and tests
without depending on the PostgreSQL implementation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AssetType(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    FONT = "font"
    DOCUMENT = "document"
    LICENSE_EVIDENCE = "license_evidence"
    GENERATED_GRAPHIC = "generated_graphic"
    VOICE = "voice"


class AssetSourceType(StrEnum):
    OWNED = "owned"
    COMMISSIONED = "commissioned"
    LICENSED = "licensed"
    STOCK = "stock"
    CREATIVE_COMMONS = "creative_commons"
    PUBLIC_DOMAIN = "public_domain"
    AI_GENERATED = "ai_generated"
    CLIENT_SUPPLIED = "client_supplied"
    UNKNOWN = "unknown"


class AssetLifecycleStatus(StrEnum):
    CANDIDATE = "candidate"
    INTERNAL_ONLY = "internal_only"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DELETED = "deleted"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"
    AWAITING_HUMAN = "awaiting_human"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class ProviderCallStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderMode(StrEnum):
    PREVIEW = "preview"
    PUBLISH = "publish"


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QualityOutcome(StrEnum):
    PASS = "pass"
    PASS_WITH_DISCLOSURE = "pass_with_disclosure"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    BLOCK = "block"


class ContentItemCreate(FrozenRecord):
    slug: str = Field(min_length=1, max_length=200)
    working_title: str = Field(min_length=1, max_length=500)
    lifecycle_status: str = "draft"
    primary_platform: str | None = None
    content_format: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentItem(ContentItemCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AssetCreate(FrozenRecord):
    asset_type: AssetType
    source_type: AssetSourceType = AssetSourceType.UNKNOWN
    lifecycle_status: AssetLifecycleStatus = AssetLifecycleStatus.CANDIDATE
    storage_uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    parent_asset_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class Asset(AssetCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AssetRightsCreate(FrozenRecord):
    asset_id: UUID
    rights_basis: AssetSourceType = AssetSourceType.UNKNOWN
    supersedes_rights_id: UUID | None = None
    asset_owner: str | None = None
    licensor: str | None = None
    license_type: str | None = None
    license_version: str | None = None
    license_url: str | None = None
    terms_snapshot_uri: str | None = None
    terms_snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    commercial_use_allowed: bool = False
    editorial_use_allowed: bool = False
    modification_allowed: bool = False
    synthetic_edit_allowed: bool = False
    attribution_required: bool = False
    attribution_text: str | None = None
    territories: list[str] = Field(default_factory=lambda: ["worldwide"])
    platforms: list[str] = Field(default_factory=list)
    campaigns: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    review_due_at: datetime | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None


class AssetRights(AssetRightsCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class WorkflowRunCreate(FrozenRecord):
    content_item_id: UUID
    workflow_name: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_budget_usd: Decimal | None = Field(default=None, ge=0)
    current_stage: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(WorkflowRunCreate):
    id: UUID
    status: WorkflowStatus
    actual_cost_usd: Decimal
    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StageExecutionCreate(FrozenRecord):
    workflow_run_id: UUID
    stage_name: str = Field(min_length=1)
    stage_version: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt: int = Field(default=1, ge=1)
    status: StageStatus = StageStatus.PENDING
    model_or_tool: str | None = None
    prompt_version: str | None = None
    timeout_seconds: int | None = Field(default=None, gt=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    operator: str | None = None


class StageExecution(StageExecutionCreate):
    id: UUID
    output_hash: str | None = None
    actual_cost_usd: Decimal
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int
    warnings: list[Any]
    output: dict[str, Any] | None = None
    failure_reason: str | None = None
    created_at: datetime


class HumanReviewCreate(FrozenRecord):
    workflow_run_id: UUID
    review_type: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    stage_execution_id: UUID | None = None
    checklist: dict[str, Any] = Field(default_factory=dict)


class HumanReview(HumanReviewCreate):
    id: UUID
    created_at: datetime


class ProviderCallCreate(FrozenRecord):
    stage_execution_id: UUID
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ProviderCallStatus = ProviderCallStatus.PENDING
    provider_request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderCall(ProviderCallCreate):
    id: UUID
    response_fingerprint: str | None = None
    units: Decimal | None = None
    unit_name: str | None = None
    cost_usd: Decimal
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class CostEntryCreate(FrozenRecord):
    workflow_run_id: UUID
    category: str = Field(min_length=1)
    amount_usd: Decimal = Field(ge=0)
    stage_execution_id: UUID | None = None
    provider_call_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None


class CostEntry(CostEntryCreate):
    id: UUID
    created_at: datetime


class RenderManifestCreate(FrozenRecord):
    content_item_id: UUID
    workflow_run_id: UUID
    mode: RenderMode
    platform: str = Field(min_length=1)
    aspect_ratio: str = Field(min_length=1)
    brand_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    manifest: dict[str, Any]
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_version: int = Field(default=1, ge=1)
    script_version: str | None = None
    storyboard_version: str | None = None
    ai_disclosure_required: bool = False
    ai_disclosure_reason: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


class RenderManifest(RenderManifestCreate):
    id: UUID
    created_at: datetime


class RenderJobCreate(FrozenRecord):
    render_manifest_id: UUID
    status: RenderJobStatus = RenderJobStatus.PENDING


class RenderJob(RenderJobCreate):
    id: UUID
    output_asset_id: UUID | None = None
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class QualityReportCreate(FrozenRecord):
    render_job_id: UUID
    overall_status: QualityOutcome
    checks: dict[str, Any] = Field(default_factory=dict)
    blocking_failures: list[Any] = Field(default_factory=list)


class QualityReport(QualityReportCreate):
    id: UUID
    created_at: datetime
