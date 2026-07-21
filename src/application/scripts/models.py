from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ScriptVersionStatus(StrEnum):
    WORKING = "working"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ScriptDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class ScriptAdapterMode(StrEnum):
    DETERMINISTIC = "deterministic"
    LOCAL_MODEL = "local_model"
    MANUAL = "manual"


class ClaimType(StrEnum):
    FACTUAL = "factual"
    INFERENCE = "inference"
    OPINION = "opinion"
    UNCERTAIN = "uncertain"


class ClaimSupportStatus(StrEnum):
    SUPPORTED = "supported"
    NEEDS_SOURCE = "needs_source"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


class ClaimSensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceType(StrEnum):
    PRIMARY = "primary"
    GOVERNMENT = "government"
    ACADEMIC = "academic"
    SECONDARY = "secondary"
    NEWS = "news"
    EXPERT = "expert"
    INTERNAL_REFERENCE = "internal_reference"


class SourceRightsDeclaration(StrEnum):
    OWNED = "owned"
    LICENSED = "licensed"
    PUBLICLY_ACCESSIBLE = "publicly_accessible"
    QUOTATION_ONLY = "quotation_only"
    INTERNAL_RESEARCH = "internal_research"


class ClaimSupportType(StrEnum):
    DIRECT = "direct"
    CORROBORATING = "corroborating"
    CONTEXTUAL = "contextual"
    LIMITATION = "limitation"


class ScriptReviewActionType(StrEnum):
    INLINE_EDIT = "inline_edit"
    FACTUAL_QUERY = "factual_query"
    SOURCE_REQUEST = "source_request"
    TONE_CHANGE = "tone_change"
    GENERAL = "general"


class ScriptSectionDraft(BaseModel):
    section_key: str = Field(min_length=1, max_length=100)
    section_type: str = Field(pattern=r"^(hook|narration|cta)$")
    text: str = Field(min_length=1, max_length=10000)
    target_duration_seconds: float = Field(gt=0, le=3600)


class ScenePlanDraft(BaseModel):
    scene_key: str = Field(min_length=1, max_length=100)
    section_key: str = Field(min_length=1, max_length=100)
    narration_text: str = Field(min_length=1, max_length=10000)
    visual_brief: str = Field(min_length=10, max_length=5000)
    on_screen_text: str | None = Field(default=None, max_length=1000)
    target_duration_seconds: float = Field(gt=0, le=3600)
    source_requirements: list[str] = Field(default_factory=list, max_length=20)


class ClaimDraft(BaseModel):
    claim_key: str = Field(min_length=1, max_length=100)
    section_key: str = Field(min_length=1, max_length=100)
    claim_text: str = Field(min_length=3, max_length=5000)
    claim_type: ClaimType
    confidence: float = Field(ge=0, le=1)
    sensitivity: ClaimSensitivity = ClaimSensitivity.LOW
    support_status: ClaimSupportStatus = ClaimSupportStatus.NEEDS_SOURCE
    wording_limitations: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def factual_claim_needs_support_state(self) -> "ClaimDraft":
        if self.claim_type == ClaimType.FACTUAL and self.support_status == ClaimSupportStatus.NOT_APPLICABLE:
            raise ValueError("Factual claims cannot be marked not applicable for source support")
        return self


class SourceDraft(BaseModel):
    source_key: str = Field(min_length=1, max_length=100)
    source_type: SourceType
    title: str = Field(min_length=3, max_length=1000)
    publisher: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=4000)
    published_on: date | None = None
    quality_score: float = Field(ge=0, le=100)
    rights_declaration: SourceRightsDeclaration
    permitted_use: str = Field(min_length=3, max_length=2000)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes: str | None = Field(default=None, max_length=5000)


class ClaimSourceDraft(BaseModel):
    claim_key: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=100)
    support_type: ClaimSupportType
    locator: str | None = Field(default=None, max_length=1000)
    support_note: str = Field(min_length=3, max_length=5000)


class ScriptDraft(BaseModel):
    platform: str = Field(min_length=1, max_length=100)
    format: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=50)
    target_duration_seconds: float = Field(gt=0, le=3600)
    words_per_minute: float = Field(default=150, ge=60, le=260)
    duration_tolerance_percent: float = Field(default=10, ge=0, le=30)
    hook_text: str = Field(min_length=1, max_length=2000)
    cta_text: str = Field(min_length=1, max_length=2000)
    sections: list[ScriptSectionDraft] = Field(min_length=1, max_length=100)
    scenes: list[ScenePlanDraft] = Field(min_length=1, max_length=100)
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=300)
    sources: list[SourceDraft] = Field(default_factory=list, max_length=300)
    claim_sources: list[ClaimSourceDraft] = Field(default_factory=list, max_length=1000)
    generation_evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_relationships(self) -> "ScriptDraft":
        section_keys = [item.section_key for item in self.sections]
        if len(section_keys) != len(set(section_keys)):
            raise ValueError("Script section keys must be unique")
        if not any(item.section_type == "hook" for item in self.sections):
            raise ValueError("Script requires a hook section")
        if not any(item.section_type == "cta" for item in self.sections):
            raise ValueError("Script requires a CTA section")
        scene_keys = [item.scene_key for item in self.scenes]
        if len(scene_keys) != len(set(scene_keys)):
            raise ValueError("Scene keys must be unique")
        unknown_scene_sections = sorted({item.section_key for item in self.scenes} - set(section_keys))
        if unknown_scene_sections:
            raise ValueError(f"Scenes reference unknown sections: {unknown_scene_sections}")
        claim_keys = [item.claim_key for item in self.claims]
        if len(claim_keys) != len(set(claim_keys)):
            raise ValueError("Claim keys must be unique")
        unknown_claim_sections = sorted({item.section_key for item in self.claims} - set(section_keys))
        if unknown_claim_sections:
            raise ValueError(f"Claims reference unknown sections: {unknown_claim_sections}")
        source_keys = [item.source_key for item in self.sources]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("Source keys must be unique")
        for link in self.claim_sources:
            if link.claim_key not in set(claim_keys):
                raise ValueError(f"Claim-source link references unknown claim: {link.claim_key}")
            if link.source_key not in set(source_keys):
                raise ValueError(f"Claim-source link references unknown source: {link.source_key}")
        return self


class ScriptGenerateRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=100)
    format: str = Field(min_length=1, max_length=100)
    language: str = Field(default="en-US", min_length=2, max_length=50)
    target_duration_seconds: float = Field(gt=0, le=3600)
    words_per_minute: float = Field(default=150, ge=60, le=260)
    duration_tolerance_percent: float = Field(default=10, ge=0, le=30)
    seed: int = Field(default=1, ge=0, le=2_147_483_647)
    adapter_mode: ScriptAdapterMode = ScriptAdapterMode.DETERMINISTIC
    local_endpoint: str | None = Field(default=None, max_length=2000)
    local_model_id: str | None = Field(default=None, max_length=300)
    local_timeout_seconds: int = Field(default=20, ge=1, le=120)

    @model_validator(mode="after")
    def local_model_requires_id(self) -> "ScriptGenerateRequest":
        if self.adapter_mode == ScriptAdapterMode.LOCAL_MODEL and not self.local_model_id:
            raise ValueError("local_model_id is required for local model generation")
        return self


class ReplaceScriptDraftRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    draft: ScriptDraft


class SubmitScriptRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)


class ScriptDecisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    decision: ScriptDecision
    rationale: str = Field(min_length=3, max_length=5000)


class ScriptRevisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=5000)


class ScriptReviewActionRequest(BaseModel):
    script_version_id: UUID
    script_section_id: UUID | None = None
    claim_id: UUID | None = None
    action_type: ScriptReviewActionType
    body: str = Field(min_length=1, max_length=5000)
    suggested_text: str | None = Field(default=None, max_length=5000)


class SourceSupportUpdateRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    sources: list[SourceDraft] = Field(default_factory=list, max_length=300)
    claim_sources: list[ClaimSourceDraft] = Field(default_factory=list, max_length=1000)
    supported_claim_keys: list[str] = Field(default_factory=list, max_length=300)
