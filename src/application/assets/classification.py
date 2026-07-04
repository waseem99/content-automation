from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from src.domain.asset_enums import AssetType
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType


class AssetContext(StrEnum):
    SOURCE_MATCH_VIDEO = "source_match_video"
    EXTRACTED_MATCH_CLIP = "extracted_match_clip"
    WEB_IMAGE_SOURCE = "web_image_source"
    WEB_IMAGE_DERIVATIVE = "web_image_derivative"
    AI_GENERATED_VISUAL = "ai_generated_visual"
    GENERATED_VOICEOVER = "generated_voiceover"
    RIGHTS_EVIDENCE = "rights_evidence"
    BACKGROUND_MUSIC = "background_music"
    FONT = "font"
    PREVIEW_RENDER = "preview_render"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AssetClassification:
    asset_type: AssetType
    source_type: AssetSourceType
    lifecycle_status: AssetLifecycleStatus


class AssetClassificationPolicy:
    _POLICY = {
        AssetContext.SOURCE_MATCH_VIDEO: AssetClassification(
            AssetType.VIDEO,
            AssetSourceType.CLIENT_SUPPLIED,
            AssetLifecycleStatus.INTERNAL_ONLY,
        ),
        AssetContext.EXTRACTED_MATCH_CLIP: AssetClassification(
            AssetType.VIDEO,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.INTERNAL_ONLY,
        ),
        AssetContext.WEB_IMAGE_SOURCE: AssetClassification(
            AssetType.IMAGE,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.WEB_IMAGE_DERIVATIVE: AssetClassification(
            AssetType.IMAGE,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.AI_GENERATED_VISUAL: AssetClassification(
            AssetType.GENERATED_GRAPHIC,
            AssetSourceType.AI_GENERATED,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.GENERATED_VOICEOVER: AssetClassification(
            AssetType.AUDIO,
            AssetSourceType.AI_GENERATED,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.RIGHTS_EVIDENCE: AssetClassification(
            AssetType.LICENSE_EVIDENCE,
            AssetSourceType.CLIENT_SUPPLIED,
            AssetLifecycleStatus.INTERNAL_ONLY,
        ),
        AssetContext.BACKGROUND_MUSIC: AssetClassification(
            AssetType.AUDIO,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.FONT: AssetClassification(
            AssetType.FONT,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.CANDIDATE,
        ),
        AssetContext.PREVIEW_RENDER: AssetClassification(
            AssetType.VIDEO,
            AssetSourceType.OWNED,
            AssetLifecycleStatus.INTERNAL_ONLY,
        ),
    }

    def classify(self, context: AssetContext, path: Path | None = None) -> AssetClassification:
        if context in self._POLICY:
            return self._POLICY[context]
        if path is None:
            return AssetClassification(
                AssetType.DOCUMENT,
                AssetSourceType.UNKNOWN,
                AssetLifecycleStatus.CANDIDATE,
            )
        suffix = path.suffix.lower()
        if suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            asset_type = AssetType.VIDEO
        elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            asset_type = AssetType.IMAGE
        elif suffix in {".mp3", ".wav", ".aac", ".m4a", ".flac"}:
            asset_type = AssetType.AUDIO
        elif suffix in {".ttf", ".otf", ".woff", ".woff2"}:
            asset_type = AssetType.FONT
        else:
            asset_type = AssetType.DOCUMENT
        return AssetClassification(
            asset_type,
            AssetSourceType.UNKNOWN,
            AssetLifecycleStatus.CANDIDATE,
        )
