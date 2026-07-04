from __future__ import annotations

from pathlib import Path

from moviepy import VideoFileClip

from src.assembler.preview_watermark import (
    DEFAULT_WATERMARK,
    apply_preview_watermark,
    write_preview_metadata,
)
from src.assembler.video_assembler import assemble_video
from src.config import Settings
from src.domain.render_status import RenderMode
from src.generator.models import ProductionPlan


def validate_short_form_publish_plan(plan: ProductionPlan) -> None:
    segments = sorted(plan.segments, key=lambda item: item.order)
    if not segments:
        raise ValueError("Publish plan has no segments")
    first = segments[0]
    if first.type == "intro" and not first.narration.strip():
        raise ValueError("Publish plan cannot begin with a dedicated logo-only intro")


def assemble_mode_video(
    *,
    plan: ProductionPlan,
    run_dir: Path,
    image_paths: dict[str, Path],
    narration_paths: dict[int, Path],
    output_path: Path,
    settings: Settings,
    source_manifest: dict | None,
    mode: RenderMode,
    watermark_text: str | None = None,
) -> Path:
    if mode == RenderMode.PUBLISH:
        validate_short_form_publish_plan(plan)
        return assemble_video(
            plan=plan,
            run_dir=run_dir,
            image_paths=image_paths,
            narration_paths=narration_paths,
            output_path=output_path,
            settings=settings,
            manifest=source_manifest,
        )

    raw_path = output_path.with_name(f"{output_path.stem}_unwatermarked{output_path.suffix}")
    assemble_video(
        plan=plan,
        run_dir=run_dir,
        image_paths=image_paths,
        narration_paths=narration_paths,
        output_path=raw_path,
        settings=settings,
        manifest=source_manifest,
    )
    source = VideoFileClip(str(raw_path))
    watermarked = apply_preview_watermark(
        source,
        text=watermark_text or DEFAULT_WATERMARK,
    )
    try:
        watermarked.write_videofile(
            str(output_path),
            fps=settings.video_fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(output_path.parent / "preview-temp-audio.m4a"),
            remove_temp=True,
            logger="bar",
        )
    finally:
        watermarked.close()
        source.close()
        raw_path.unlink(missing_ok=True)
    write_preview_metadata(
        output_path,
        watermark_text=watermark_text or DEFAULT_WATERMARK,
    )
    return output_path
