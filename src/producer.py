"""Orchestrate script, images, voiceover, and final video assembly."""

from __future__ import annotations

import json
from pathlib import Path

from src.config import Settings
from src.generator.match_context import build_match_context
from src.generator.models import ProductionPlan
from src.generator.script_generator import generate_production_plan


def _progress(message: str) -> None:
    print(message, flush=True)


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _clip_labels_from_manifest(manifest: dict) -> dict[str, str]:
    return {clip["file"]: clip.get("label", "moment") for clip in manifest.get("clips", [])}


def _apply_cli_clips_to_plan(plan: ProductionPlan, clip_files: list[str]) -> ProductionPlan:
    """Always use clip filenames from the CLI, not whatever is saved in the plan."""
    clip_segments = sorted(plan.clip_segments(), key=lambda s: s.order)
    if len(clip_segments) != len(clip_files):
        raise ValueError(
            f"Production plan has {len(clip_segments)} clip segment(s) but CLI provided "
            f"{len(clip_files)} clip(s). Run with --regenerate-script to rebuild the plan."
        )
    for segment, clip_file in zip(clip_segments, clip_files):
        segment.clip_file = clip_file
    return plan


def _resolve_existing_images(plan: ProductionPlan, production_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for segment in plan.visual_segments():
        if segment.type == "intro":
            path = production_dir / "image_intro.png"
            if path.exists():
                paths["intro"] = path
        elif segment.image_index is not None:
            path = production_dir / f"image_{segment.image_index:02d}.png"
            if path.exists():
                paths[str(segment.image_index)] = path
    return paths


def run_production(
    run_dir: Path,
    topic: str,
    clip_files: list[str],
    settings: Settings,
    skip_images: bool = False,
    skip_voice: bool = False,
    skip_assembly: bool = False,
    regenerate_script: bool = False,
    plan_path: Path | None = None,
) -> dict:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {run_dir}")

    production_dir = run_dir / "production"
    production_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)
    clip_labels = _clip_labels_from_manifest(manifest)

    for clip_file in clip_files:
        if not (run_dir / clip_file).exists():
            raise FileNotFoundError(f"Clip not found in run folder: {run_dir / clip_file}")

    saved_plan_path = plan_path or production_dir / "production_plan.json"

    if saved_plan_path.exists() and not regenerate_script:
        _progress("Loading saved production plan...")
        plan = ProductionPlan.model_validate(
            json.loads(saved_plan_path.read_text(encoding="utf-8"))
        )
    else:
        _progress("Building match context (Whisper may take 1-3 min on first run)...")
        match_context = build_match_context(manifest, run_dir, clip_files, settings)
        (production_dir / "match_context.txt").write_text(match_context, encoding="utf-8")
        _progress("Generating script via OpenAI...")
        plan = generate_production_plan(
            topic=topic,
            clip_files=clip_files,
            clip_labels=clip_labels,
            match_context=match_context,
            settings=settings,
        )
        saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    plan = _apply_cli_clips_to_plan(plan, clip_files)
    saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    image_paths: dict[str, Path] = {}
    if not skip_images:
        from src.generator.image_generator import generate_images

        _progress("Fetching web images via SerpAPI (one per segment)...")
        image_paths = generate_images(plan, production_dir, settings)
    else:
        _progress("Skipping image fetch (--skip-images)...")
        image_paths = _resolve_existing_images(plan, production_dir)

    narration_paths: dict[int, Path] = {}
    if not skip_voice:
        from src.generator.voice_generator import generate_voiceovers

        _progress("Generating voiceovers via ElevenLabs...")
        narration_paths = generate_voiceovers(plan, production_dir, settings)
    else:
        _progress("Skipping voice generation (--skip-voice)...")
        for segment in plan.narrated_segments():
            path = production_dir / f"narration_{segment.order:02d}.mp3"
            if path.exists():
                narration_paths[segment.order] = path

    final_video_path = production_dir / "final_video.mp4"
    if not skip_assembly:
        from src.assembler.video_assembler import assemble_video

        _progress("Assembling final video (often 5-15 min on CPU — progress bar below)...")
        assemble_video(
            plan=plan,
            run_dir=run_dir,
            image_paths=image_paths,
            narration_paths=narration_paths,
            output_path=final_video_path,
            settings=settings,
            manifest=manifest,
        )

    return {
        "plan_path": saved_plan_path,
        "production_dir": production_dir,
        "final_video": final_video_path if not skip_assembly else None,
        "image_paths": image_paths,
        "narration_paths": narration_paths,
    }
