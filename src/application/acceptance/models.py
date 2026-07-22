from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PilotStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    BLOCKED = "blocked"
    ACCEPTED = "accepted"
    RETIRED = "retired"


class ProductionMode(StrEnum):
    LOCAL_ONLY = "local_only"
    MANAGED_RENDER = "managed_render"


class EvidenceCategory(StrEnum):
    BRAND_PROFILE = "brand_profile"
    NARRATION_PRESET = "narration_preset"
    ROLE_ASSIGNMENT = "role_assignment"
    CONCEPT_APPROVAL = "concept_approval"
    SOURCE_EVIDENCE = "source_evidence"
    SCRIPT_APPROVAL = "script_approval"
    SCRIPT_REVISION = "script_revision"
    NARRATION_APPROVAL = "narration_approval"
    NARRATION_REVISION = "narration_revision"
    VISUAL_APPROVAL = "visual_approval"
    VISUAL_REVISION = "visual_revision"
    ROUTING_EXPLANATION = "routing_explanation"
    SPEND_APPROVAL = "spend_approval"
    RENDERER_LINEAGE = "renderer_lineage"
    ARTIFACT_LINEAGE = "artifact_lineage"
    FINAL_QA = "final_qa"
    RELEASE_MANIFEST = "release_manifest"
    PUBLISHER_DECISION = "publisher_decision"
    STAGING_DELIVERY = "staging_delivery"
    ANALYTICS_OBSERVATION = "analytics_observation"
    PRODUCTION_ECONOMICS = "production_economics"
    BACKUP_RESTORE = "backup_restore"
    WORKER_RESTART = "worker_restart"
    RUNBOOK_VALIDATION = "runbook_validation"


class DefectSeverity(StrEnum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class DefectResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    WAIVED = "waived"


class SignoffRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"


class SignoffDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class LiveResultStatus(StrEnum):
    SUBMITTED = "submitted"
    PUBLISHED = "published"
    FAILED = "failed"
    REMOVED = "removed"


class PilotCreateRequest(BaseModel):
    pilot_key: str = Field(min_length=8, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    acceptance_policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator("pilot_key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    def canonical_scope(self) -> dict[str, Any]:
        return {
            "brand_slugs": ["animal-x", "rawr-nation"],
            "items_per_brand": 2,
            "total_items": 4,
            "required_modes": ["local_only", "managed_render"],
            "staging_delivery": "simulated_only",
            "live_delivery": "external_evidence_after_signoff",
        }


class PilotRetireRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=3000)


class PilotAcceptRequest(BaseModel):
    production_release_tag: str = Field(
        min_length=8,
        max_length=160,
        pattern=r"^prod-[a-z0-9][a-z0-9._-]{3,154}$",
    )
    runbook_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("production_release_tag", mode="before")
    @classmethod
    def normalize_release_tag(cls, value: str) -> str:
        return value.strip().lower()


class PilotItemRequest(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    production_mode: ProductionMode
    live_delivery_evidence_required: bool = False
    required_revision_stages: tuple[str, ...] = ("script", "narration", "visual")

    @field_validator("required_revision_stages", mode="before")
    @classmethod
    def normalize_revision_stages(cls, values) -> tuple[str, ...]:
        normalized = tuple(sorted({str(value).strip().lower() for value in values if str(value).strip()}))
        return normalized

    @model_validator(mode="after")
    def validate_revision_scope(self) -> "PilotItemRequest":
        allowed = {"script", "narration", "visual"}
        if not self.required_revision_stages or not set(self.required_revision_stages).issubset(allowed):
            raise ValueError("required_revision_stages must contain script, narration, or visual")
        return self


class EvidenceCollectRequest(BaseModel):
    categories: tuple[EvidenceCategory, ...] = tuple(EvidenceCategory)

    @field_validator("categories", mode="before")
    @classmethod
    def deduplicate_categories(cls, values) -> tuple[EvidenceCategory, ...]:
        return tuple(dict.fromkeys(EvidenceCategory(value) for value in values))


class OperationsEvidenceRequest(BaseModel):
    category: EvidenceCategory
    subject_type: str = Field(min_length=2, max_length=120)
    subject_id: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def operations_only(self) -> "OperationsEvidenceRequest":
        allowed = {
            EvidenceCategory.BACKUP_RESTORE,
            EvidenceCategory.WORKER_RESTART,
            EvidenceCategory.RUNBOOK_VALIDATION,
        }
        if self.category not in allowed:
            raise ValueError("manual subject binding is limited to operations evidence")
        return self


class DefectOpenRequest(BaseModel):
    pilot_item_id: UUID | None = None
    defect_key: str = Field(min_length=5, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    severity: DefectSeverity
    summary: str = Field(min_length=3, max_length=1000)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DefectResolveRequest(BaseModel):
    status: DefectResolutionStatus
    resolution: str = Field(min_length=3, max_length=3000)


class SignoffRequest(BaseModel):
    role: SignoffRole
    decision: SignoffDecision
    rationale: str = Field(min_length=3, max_length=2000)


class LiveDeliveryEvidenceRequest(BaseModel):
    pilot_item_id: UUID
    final_release_id: UUID
    platform: str = Field(min_length=2, max_length=80)
    platform_reference: str = Field(min_length=3, max_length=500)
    result_status: LiveResultStatus
    external_response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: dict[str, Any]

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: str) -> str:
        return value.strip().lower()
