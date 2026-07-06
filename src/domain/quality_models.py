from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class QualityOutcome(StrEnum):
    PASS = "pass"
    PASS_WITH_DISCLOSURE = "pass_with_disclosure"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    BLOCK = "block"


class QualitySeverity(StrEnum):
    INFO = "info"
    DISCLOSURE = "disclosure"
    HUMAN_REVIEW = "human_review"
    BLOCK = "block"


class QualityCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class QualityFailureCode(StrEnum):
    RENDER_NOT_SUCCEEDED = "RENDER_NOT_SUCCEEDED"
    OUTPUT_ASSET_MISSING = "OUTPUT_ASSET_MISSING"
    OUTPUT_CORRUPTION = "OUTPUT_CORRUPTION"
    OUTPUT_HASH_MISMATCH = "OUTPUT_HASH_MISMATCH"
    MANIFEST_NOT_APPROVED = "MANIFEST_NOT_APPROVED"
    PLACEHOLDER_ASSET = "PLACEHOLDER_ASSET"
    PREVIEW_WATERMARK = "PREVIEW_WATERMARK"
    NOT_FOR_PUBLICATION = "NOT_FOR_PUBLICATION"
    ASSET_HASH_MISMATCH = "ASSET_HASH_MISMATCH"
    RIGHTS_NOT_APPROVED = "RIGHTS_NOT_APPROVED"
    UNAPPROVED_MATCH_FOOTAGE = "UNAPPROVED_MATCH_FOOTAGE"
    MUSIC_RIGHTS_NOT_APPROVED = "MUSIC_RIGHTS_NOT_APPROVED"
    VOICE_NOT_APPROVED = "VOICE_NOT_APPROVED"
    FONT_RIGHTS_NOT_APPROVED = "FONT_RIGHTS_NOT_APPROVED"
    DISCLOSURE_REQUIRED = "DISCLOSURE_REQUIRED"
    RESOLUTION_MISMATCH = "RESOLUTION_MISMATCH"
    ASPECT_RATIO_MISMATCH = "ASPECT_RATIO_MISMATCH"
    FRAME_RATE_MISMATCH = "FRAME_RATE_MISMATCH"
    DURATION_INVALID = "DURATION_INVALID"
    BLACK_FRAMES_DETECTED = "BLACK_FRAMES_DETECTED"
    FROZEN_FRAMES_DETECTED = "FROZEN_FRAMES_DETECTED"
    CAPTION_CLIPPING = "CAPTION_CLIPPING"
    SAFE_AREA_VIOLATION = "SAFE_AREA_VIOLATION"
    AUDIO_MISSING = "AUDIO_MISSING"
    HUMAN_REVIEW_NEEDED = "HUMAN_REVIEW_NEEDED"


class MediaInspection(FrozenRecord):
    valid_container: bool = True
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fps: float | None = Field(default=None, gt=0)
    duration_sec: float | None = Field(default=None, gt=0)
    has_audio: bool | None = None
    black_frames_detected: bool = False
    frozen_frames_detected: bool = False
    caption_clipping_detected: bool = False
    safe_area_violation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityCheckResult(FrozenRecord):
    code: str = Field(min_length=1)
    status: QualityCheckStatus
    severity: QualitySeverity = QualitySeverity.INFO
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReportCreate(FrozenRecord):
    render_job_id: UUID
    render_manifest_id: UUID | None = None
    output_asset_id: UUID | None = None
    overall_status: QualityOutcome
    checks: dict[str, Any]
    blocking_failures: list[str] = Field(default_factory=list)
    check_registry_version: str = Field(default="quality-gate-v1", min_length=1)
    input_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    report_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    disclosure_texts: list[str] = Field(default_factory=list)
    human_review_reasons: list[str] = Field(default_factory=list)
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityReport(QualityReportCreate):
    id: UUID
    created_at: datetime
