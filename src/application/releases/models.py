from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ReleaseInputRole(StrEnum):
    NARRATION = "narration"
    VISUAL_SHOT = "visual_shot"
    GRAPHIC = "graphic"
    CAPTIONS = "captions"
    MUSIC = "music"
    BRANDING = "branding"
    PLATFORM_METADATA = "platform_metadata"
    DISCLOSURE = "disclosure"


class ReleaseStatus(StrEnum):
    DRAFT = "draft"
    ASSEMBLY_QUEUED = "assembly_queued"
    ASSEMBLED = "assembled"
    QA_COMPLETE = "qa_complete"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class QaOutcome(StrEnum):
    PASS = "pass"
    BLOCK = "block"


class PlaybackDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class RenderProfileRequest(BaseModel):
    profile_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=3, max_length=200)
    platform: str = Field(min_length=2, max_length=80)
    width: int = Field(ge=64, le=16384)
    height: int = Field(ge=64, le=16384)
    fps: Decimal = Field(gt=0, le=240)
    container: str = Field(min_length=2, max_length=20)
    video_codec: str = Field(min_length=2, max_length=80)
    audio_codec: str = Field(min_length=2, max_length=80)
    video_bitrate_kbps: int = Field(gt=0, le=1_000_000)
    audio_bitrate_kbps: int = Field(gt=0, le=10_000)
    min_duration_seconds: Decimal = Field(default=Decimal("0.1"), gt=0, le=86400)
    max_duration_seconds: Decimal = Field(gt=0, le=86400)
    safe_area: dict[str, int] = Field(default_factory=dict)
    captions_required: bool = True
    caption_format: str = Field(default="burned_in", pattern=r"^(burned_in|sidecar|either)$")
    watermark_policy: str = Field(default="forbidden", pattern=r"^(forbidden|required|optional)$")
    disclosure_required: bool = False
    target_loudness_lufs: Decimal = Field(default=Decimal("-14"), ge=-60, le=0)
    loudness_tolerance_lu: Decimal = Field(default=Decimal("2"), gt=0, le=20)
    max_true_peak_dbfs: Decimal = Field(default=Decimal("-1"), ge=-20, le=0)
    max_av_sync_offset_ms: int = Field(default=80, ge=0, le=5000)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "profile_key", "platform", "container", "video_codec", "audio_codec", "caption_format", "watermark_policy",
        mode="before",
    )
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_ranges(self) -> "RenderProfileRequest":
        if self.max_duration_seconds < self.min_duration_seconds:
            raise ValueError("max_duration_seconds must be greater than or equal to min_duration_seconds")
        required_edges = {"top", "right", "bottom", "left"}
        if set(self.safe_area) != required_edges or any(value < 0 for value in self.safe_area.values()):
            raise ValueError("safe_area requires non-negative top, right, bottom, and left values")
        if self.safe_area["left"] + self.safe_area["right"] >= self.width:
            raise ValueError("horizontal safe area consumes the output width")
        if self.safe_area["top"] + self.safe_area["bottom"] >= self.height:
            raise ValueError("vertical safe area consumes the output height")
        return self


class ReleaseInputApprovalRequest(BaseModel):
    artifact_version_id: UUID
    role: ReleaseInputRole
    decision: str = Field(pattern=r"^(approved|rejected)$")
    rationale: str = Field(min_length=3, max_length=5000)


class ReleaseInputRequest(BaseModel):
    artifact_version_id: UUID
    role: ReleaseInputRole
    sequence_number: int = Field(default=0, ge=0, le=10000)
    required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalReleaseCreate(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    render_profile_id: UUID
    audio_mix_version_id: UUID
    routing_plan_id: UUID | None = None
    inputs: tuple[ReleaseInputRequest, ...] = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_inputs(self) -> "FinalReleaseCreate":
        identities = [
            (item.role.value, item.sequence_number, str(item.artifact_version_id))
            for item in self.inputs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("release inputs must be unique by role, sequence, and artifact version")
        required_roles = {ReleaseInputRole.NARRATION, ReleaseInputRole.VISUAL_SHOT, ReleaseInputRole.BRANDING}
        present = {item.role for item in self.inputs if item.required}
        missing = sorted(role.value for role in required_roles - present)
        if missing:
            raise ValueError(f"required release roles are missing: {', '.join(missing)}")
        return self


class AssemblyEnqueueRequest(BaseModel):
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    priority: int = Field(default=0, ge=-1000, le=1000)
    timeout_seconds: int = Field(default=1800, ge=30, le=86400)
    max_attempts: int = Field(default=2, ge=1, le=10)


class AssemblyOutputRequest(BaseModel):
    output_artifact_version_id: UUID
    generation_job_id: UUID


class TechnicalInspection(BaseModel):
    valid_container: bool
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: Decimal | None = Field(default=None, ge=0)
    duration_seconds: Decimal | None = Field(default=None, ge=0)
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    video_bitrate_kbps: int | None = Field(default=None, ge=0)
    audio_bitrate_kbps: int | None = Field(default=None, ge=0)
    has_audio: bool | None = None
    captions_present: bool | None = None
    caption_format: str | None = None
    disclosure_present: bool | None = None
    watermark_present: bool | None = None
    missing_frame_count: int = Field(default=0, ge=0)
    frozen_segment_count: int = Field(default=0, ge=0)
    black_frame_count: int = Field(default=0, ge=0)
    duplicate_shot_pairs: tuple[tuple[int, int], ...] = ()
    caption_timing_violation_count: int = Field(default=0, ge=0)
    caption_clipping_detected: bool = False
    safe_area_violation: bool = False
    av_sync_offset_ms: int | None = None
    integrated_loudness_lufs: Decimal | None = None
    true_peak_dbfs: Decimal | None = None
    audio_clipping_detected: bool = False
    file_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    details: dict[str, Any] = Field(default_factory=dict)


class QaEvaluateRequest(BaseModel):
    inspection: TechnicalInspection
    inspector_label: str = Field(min_length=2, max_length=200)


class PlaybackReviewRequest(BaseModel):
    decision: PlaybackDecision
    checklist: dict[str, bool]
    rationale: str = Field(min_length=3, max_length=5000)

    @model_validator(mode="after")
    def validate_checklist(self) -> "PlaybackReviewRequest":
        required = {
            "full_playback_completed",
            "narration_intelligible",
            "visual_order_correct",
            "captions_readable",
            "branding_correct",
            "disclosures_visible",
            "no_unintended_content",
        }
        missing = sorted(required - set(self.checklist))
        if missing:
            raise ValueError(f"playback checklist entries are missing: {', '.join(missing)}")
        if self.decision == PlaybackDecision.APPROVED and not all(self.checklist[key] for key in required):
            raise ValueError("approved playback review requires every checklist item to pass")
        return self


class ReleaseDecisionRequest(BaseModel):
    decision: PlaybackDecision
    rationale: str = Field(min_length=3, max_length=5000)
    expected_lock_version: int = Field(ge=1)
