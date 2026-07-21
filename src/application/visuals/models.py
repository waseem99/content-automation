from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CandidateCheckType(StrEnum):
    FORMAT = "format"
    CORRUPTION = "corruption"
    UNWANTED_TEXT = "unwanted_text"
    DUPLICATE = "duplicate"
    PROMPT_COVERAGE = "prompt_coverage"
    SUBJECT_CONSISTENCY = "subject_consistency"
    LANDMARK_CONSISTENCY = "landmark_consistency"
    LIGHTING_CONSISTENCY = "lighting_consistency"
    PALETTE_CONSISTENCY = "palette_consistency"
    FRAMING = "framing"


class CandidateCheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class CandidateDecision(StrEnum):
    SELECTED = "selected"
    REJECTED = "rejected"


class ShotDecision(StrEnum):
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class ProjectDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class VisualReviewActionType(StrEnum):
    PROMPT = "prompt"
    SUBJECT = "subject"
    ENVIRONMENT = "environment"
    LANDMARK = "landmark"
    LIGHTING = "lighting"
    PALETTE = "palette"
    FRAMING = "framing"
    ARTIFACT = "artifact"
    GENERAL = "general"


class VisualPresetRequest(BaseModel):
    preset_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    palette: dict[str, Any] = Field(default_factory=dict)
    subject_rules: dict[str, Any] = Field(default_factory=dict)
    environment_rules: dict[str, Any] = Field(default_factory=dict)
    camera_rules: dict[str, Any] = Field(default_factory=dict)
    lighting_rules: dict[str, Any] = Field(default_factory=dict)
    framing_rules: dict[str, Any] = Field(default_factory=dict)
    negative_prompt: str = Field(default="", max_length=5000)
    exclusions: list[str] = Field(default_factory=list, max_length=200)
    parent_preset_id: UUID | None = None


class ContinuityReferenceRequest(BaseModel):
    reference_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    reference_type: str = Field(pattern=r"^(subject|environment|landmark|palette|lighting|framing|style)$")
    asset_id: UUID | None = None
    reference_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    description: str = Field(min_length=3, max_length=5000)
    attributes: dict[str, Any] = Field(default_factory=dict)


class VisualProjectInitializeRequest(BaseModel):
    visual_preset_id: UUID
    provider: str = Field(default="comfyui-sdxl-local", pattern=r"^(comfyui-local|comfyui-sdxl-local)$")
    model_id: str = Field(default="sdxl-base-1.0", min_length=1, max_length=200)
    candidate_count: int = Field(default=3, ge=3, le=12)
    width: int = Field(default=704, ge=256, le=4096)
    height: int = Field(default=1280, ge=256, le=4096)
    base_seed: int = Field(default=910000, ge=0, le=2**63 - 1)
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    timeout_seconds: int = Field(default=900, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)
    continuity_references: list[ContinuityReferenceRequest] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def portrait_format(self) -> "VisualProjectInitializeRequest":
        if self.height <= self.width:
            raise ValueError("P91 candidate canvas must be portrait")
        return self


class CandidateCheck(BaseModel):
    check_type: CandidateCheckType
    status: CandidateCheckStatus
    score: float | None = Field(default=None, ge=0, le=100)
    evidence: dict[str, Any] = Field(default_factory=dict)
    checked_by: str = Field(min_length=1, max_length=200)


class CandidateResult(BaseModel):
    asset_id: UUID
    width: int = Field(ge=256, le=4096)
    height: int = Field(ge=256, le=4096)
    mime_type: str = Field(default="image/png", pattern=r"^image/(png|jpeg|webp)$")
    provenance: dict[str, Any]
    duplicate_candidate_id: UUID | None = None
    duplicate_similarity: float | None = Field(default=None, ge=0, le=1)
    checks: list[CandidateCheck]

    @model_validator(mode="after")
    def all_required_checks_once(self) -> "CandidateResult":
        kinds = [item.check_type for item in self.checks]
        expected = set(CandidateCheckType)
        if set(kinds) != expected or len(set(kinds)) != len(kinds):
            raise ValueError("candidate result requires each of the ten check types exactly once")
        if not self.provenance:
            raise ValueError("candidate provenance is required")
        duplicate = next(item for item in self.checks if item.check_type == CandidateCheckType.DUPLICATE)
        if duplicate.status != CandidateCheckStatus.PASS and self.duplicate_candidate_id is None:
            raise ValueError("non-passing duplicate check requires duplicate_candidate_id")
        return self


class CandidateDecisionRequest(BaseModel):
    expected_shot_lock_version: int = Field(ge=1)
    decision: CandidateDecision
    rationale: str = Field(min_length=3, max_length=5000)


class ShotDecisionRequest(BaseModel):
    expected_shot_lock_version: int = Field(ge=1)
    decision: ShotDecision
    rationale: str = Field(min_length=3, max_length=5000)


class ShotRevisionRequest(BaseModel):
    expected_shot_lock_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=5000)
    prompt_patch: dict[str, Any] = Field(default_factory=dict)
    negative_prompt_append: str = Field(default="", max_length=5000)
    base_seed: int = Field(default=920000, ge=0, le=2**63 - 1)
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    timeout_seconds: int = Field(default=900, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)


class ReviewActionRequest(BaseModel):
    expected_shot_lock_version: int = Field(ge=1)
    visual_shot_version_id: UUID
    visual_candidate_id: UUID | None = None
    action_type: VisualReviewActionType
    body: str = Field(min_length=1, max_length=5000)
    suggested_value: str | None = Field(default=None, max_length=5000)


class ResolveReviewActionRequest(BaseModel):
    expected_shot_lock_version: int = Field(ge=1)


class ProjectDecisionRequest(BaseModel):
    expected_project_lock_version: int = Field(ge=1)
    decision: ProjectDecision
    rationale: str = Field(min_length=3, max_length=5000)


class SubmitProjectRequest(BaseModel):
    expected_project_lock_version: int = Field(ge=1)
