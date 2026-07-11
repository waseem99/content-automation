from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RightsDeclaration(StrEnum):
    OWNED = "owned"
    PERMITTED = "permitted"
    PUBLIC_INTERNAL_RESEARCH = "public-internal-research"
    RIGHTS_HOLDER_UPLOAD = "rights-holder-upload"


class ProjectStatus(StrEnum):
    CREATED = "created"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class Platform(StrEnum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    X = "x"
    GOOGLE_DRIVE = "google-drive"
    LOCAL = "local"
    UNKNOWN = "unknown"


class SourceAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declaration: RightsDeclaration
    operator_note: str | None = Field(default=None, max_length=1000)
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["url", "file"]
    platform: Platform
    original_url: HttpUrl | None = None
    original_path: str | None = None
    title: str
    uploader: str | None = None
    source_sha256: str | None = None
    canonical_key: str

    @field_validator("original_path")
    @classmethod
    def no_parent_traversal(cls, value: str | None) -> str | None:
        if value and ".." in Path(value).parts:
            raise ValueError("source path may not contain parent traversal")
        return value


class MediaMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    fps: float = 0
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate: int | None = None
    orientation: Literal["portrait", "landscape", "square", "unknown"] = "unknown"
    loudness_lufs: float | None = None
    silence_intervals: list[tuple[float, float]] = Field(default_factory=list)


class FrameArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    timestamp_seconds: float
    relative_path: str
    kind: Literal["interval", "scene", "hook", "payoff", "cta"]
    preferred: bool = True
    quality_score: float = Field(default=1.0, ge=0, le=1)
    rejection_reasons: list[str] = Field(default_factory=list)


class SceneArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    start_seconds: float
    end_seconds: float
    keyframe_path: str | None = None
    detector: str
    confidence: float = Field(default=1.0, ge=0, le=1)


class TranscriptWord(BaseModel):
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None


class TranscriptSegment(BaseModel):
    id: str
    start_seconds: float
    end_seconds: float
    text: str
    words: list[TranscriptWord] = Field(default_factory=list)


class AnalysisFinding(BaseModel):
    id: str
    category: str
    label: str
    summary: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    measured: bool = False


class ObjectiveScore(BaseModel):
    score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)


class ReferenceAnalysis(BaseModel):
    schema_version: Literal["p66.reference_analysis.v1"] = "p66.reference_analysis.v1"
    hook: dict[str, Any] = Field(default_factory=dict)
    story_arc: list[dict[str, Any]] = Field(default_factory=list)
    pacing: dict[str, Any] = Field(default_factory=dict)
    visual_language: dict[str, Any] = Field(default_factory=dict)
    audio_language: dict[str, Any] = Field(default_factory=dict)
    findings: list[AnalysisFinding] = Field(default_factory=list)
    objective_scores: dict[str, ObjectiveScore] = Field(default_factory=dict)
    analyzer: dict[str, str] = Field(default_factory=dict)


class ReferenceFingerprint(BaseModel):
    schema_version: Literal["p66.reference_fingerprint.v1"] = "p66.reference_fingerprint.v1"
    reference_id: str
    title: str
    platform: Platform
    duration_seconds: float
    hook: dict[str, Any]
    story_arc: list[dict[str, Any]]
    pacing: dict[str, Any]
    visual_language: dict[str, Any]
    audio_language: dict[str, Any]
    objective_scores: dict[str, ObjectiveScore]
    reusable_mechanics: list[str]
    source_specific_elements_to_exclude: list[str]
    evidence_timestamps: list[float]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OriginalBrief(BaseModel):
    schema_version: Literal["p66.original_content_brief.v1"] = "p66.original_content_brief.v1"
    reference_id: str
    brand_id: str
    target_platform: str = "facebook_reels"
    duration_seconds: int = 60
    topic: str
    audience: str
    objective_priorities: list[str]
    hook_formula: str
    pacing_target: dict[str, Any]
    story_structure: list[str]
    caption_direction: str
    visual_direction: str
    cta_direction: str
    originality_constraints: list[str]
    source_traceability: dict[str, Any]
    human_review_required: Literal[True] = True
    status: Literal["draft_for_human_review"] = "draft_for_human_review"


class ProcessingEvent(BaseModel):
    stage: str
    status: Literal["started", "completed", "warning", "failed"]
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class ReferenceProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["p66.reference_project.v1"] = "p66.reference_project.v1"
    reference_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: ProjectStatus = ProjectStatus.CREATED
    source: SourceDescriptor
    access: SourceAccess
    workspace_path: str
    tool_versions: dict[str, str] = Field(default_factory=dict)
    media: MediaMetadata | None = None
    frames: list[FrameArtifact] = Field(default_factory=list)
    scenes: list[SceneArtifact] = Field(default_factory=list)
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    analysis: ReferenceAnalysis | None = None
    events: list[ProcessingEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
