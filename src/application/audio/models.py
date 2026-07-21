from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AudioProductionStatus(StrEnum):
    WORKING = "working"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class AudioTakeStatus(StrEnum):
    QUEUED = "queued"
    GENERATED = "generated"
    SELECTED = "selected"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class AlignmentSource(StrEnum):
    NONE = "none"
    FORCED_ALIGNMENT = "forced_alignment"
    PROPORTIONAL_PREVIEW = "proportional_preview"


class AudioDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class AudioReviewActionType(StrEnum):
    PRONUNCIATION = "pronunciation"
    PACE = "pace"
    TONE = "tone"
    PARAGRAPH_REPLACEMENT = "paragraph_replacement"
    MIX = "mix"
    GENERAL = "general"


class TrackRole(StrEnum):
    NARRATION = "narration"
    MUSIC = "music"
    SFX = "sfx"


class WordTiming(BaseModel):
    word: str = Field(min_length=1, max_length=300)
    start_seconds: float = Field(ge=0, le=86400)
    end_seconds: float = Field(gt=0, le=86400)

    @model_validator(mode="after")
    def end_after_start(self) -> "WordTiming":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("word timing end must be after start")
        return self


class AudioInitializeRequest(BaseModel):
    model_id: str = Field(default="kokoro-v1.0", min_length=1, max_length=200)
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    timeout_seconds: int = Field(default=300, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)


class PronunciationOverrideRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    token: str = Field(min_length=1, max_length=200)
    pronunciation: str = Field(min_length=1, max_length=500)
    locale: str = Field(default="en-US", min_length=2, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class AudioTakeResult(BaseModel):
    asset_id: UUID
    duration_seconds: float = Field(gt=0, le=86400)
    sample_rate_hz: int = Field(ge=8000, le=384000)
    channels: int = Field(ge=1, le=16)
    integrated_lufs: float
    true_peak_dbfs: float
    clipping_count: int = Field(ge=0)
    silence_ratio: float = Field(ge=0, le=1)
    timing_source: AlignmentSource
    word_timings: list[WordTiming] = Field(default_factory=list, max_length=10000)
    qc_evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def timings_match_source(self) -> "AudioTakeResult":
        if self.timing_source != AlignmentSource.NONE and not self.word_timings:
            raise ValueError("timed audio requires word timings")
        if self.word_timings:
            previous_end = 0.0
            for timing in self.word_timings:
                if timing.start_seconds < previous_end:
                    raise ValueError("word timings must be monotonic")
                if timing.end_seconds > self.duration_seconds + 0.05:
                    raise ValueError("word timing exceeds audio duration")
                previous_end = timing.end_seconds
        return self


class SelectTakeRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class MixTrackRequest(BaseModel):
    track_role: TrackRole
    asset_id: UUID
    asset_rights_id: UUID | None = None
    level_db: float = Field(default=0, ge=-120, le=24)
    ducking_db: float = Field(default=0, ge=-120, le=24)
    start_seconds: float = Field(default=0, ge=0, le=86400)
    end_seconds: float | None = Field(default=None, gt=0, le=86400)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rights_and_range(self) -> "MixTrackRequest":
        if self.track_role in {TrackRole.MUSIC, TrackRole.SFX} and self.asset_rights_id is None:
            raise ValueError("music and sound effects require asset_rights_id")
        if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("track end must be after start")
        return self


class MixRegistrationRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    narration_asset_id: UUID
    final_mix_asset_id: UUID
    target_lufs: float = Field(default=-16.0, ge=-40, le=-5)
    peak_limit_dbfs: float = Field(default=-1.0, ge=-12, le=0)
    measured_lufs: float
    true_peak_dbfs: float
    clipping_count: int = Field(ge=0)
    silence_ratio: float = Field(ge=0, le=1)
    duration_seconds: float = Field(gt=0, le=86400)
    waveform_metadata: dict[str, Any]
    segment_snapshot: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    mix_settings: dict[str, Any] = Field(default_factory=dict)
    alignment_source: AlignmentSource
    tracks: list[MixTrackRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def narration_track_required(self) -> "MixRegistrationRequest":
        narration = [item for item in self.tracks if item.track_role == TrackRole.NARRATION]
        if len(narration) != 1:
            raise ValueError("exactly one narration track is required")
        if narration[0].asset_id != self.narration_asset_id:
            raise ValueError("narration track asset must match narration_asset_id")
        if not self.waveform_metadata:
            raise ValueError("waveform metadata is required")
        if self.alignment_source == AlignmentSource.NONE:
            raise ValueError("mix alignment source must be recorded")
        return self


class SubmitAudioRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class ReviewActionRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    audio_mix_version_id: UUID
    paragraph_id: UUID | None = None
    segment_take_id: UUID | None = None
    action_type: AudioReviewActionType
    body: str = Field(min_length=1, max_length=5000)
    suggested_value: str | None = Field(default=None, max_length=5000)


class ResolveReviewActionRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class AudioDecisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    decision: AudioDecision
    rationale: str = Field(min_length=3, max_length=5000)


class MixRevisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=5000)


class AssemblyEnqueueRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    model_id: str = Field(default="local-ffmpeg", min_length=1, max_length=200)
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    timeout_seconds: int = Field(default=900, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)
