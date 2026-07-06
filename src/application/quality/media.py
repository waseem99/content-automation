from __future__ import annotations

from pathlib import Path

from src.domain.quality_models import MediaInspection


class MetadataMediaInspector:
    """Small deterministic inspector for controlled tests and stored metadata.

    Production deployments can replace this adapter with an ffprobe-backed implementation
    while keeping the quality gate contract stable.
    """

    def inspect(self, path: Path, metadata: dict | None = None) -> MediaInspection:
        metadata = metadata or {}
        if not path.is_file():
            return MediaInspection(valid_container=False, metadata={"missing_path": str(path)})
        media = metadata.get("media") or metadata
        return MediaInspection(
            valid_container=bool(media.get("valid_container", True)),
            width=media.get("width"),
            height=media.get("height"),
            fps=media.get("fps"),
            duration_sec=media.get("duration_sec"),
            has_audio=media.get("has_audio"),
            black_frames_detected=bool(media.get("black_frames_detected", False)),
            frozen_frames_detected=bool(media.get("frozen_frames_detected", False)),
            caption_clipping_detected=bool(media.get("caption_clipping_detected", False)),
            safe_area_violation=bool(media.get("safe_area_violation", False)),
            metadata={"path": str(path), **media},
        )
