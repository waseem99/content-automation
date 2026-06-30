"""Orchestrate explainer script, visuals, voiceover, and assembly."""

from __future__ import annotations

import json
from pathlib import Path

from src.assembler.explainer_assembler import COMPARISON_COLLAGE_FILENAME, assemble_explainer_video, reconcile_plan_with_narration
from src.concepts.loader import load_concept
from src.config import Settings
from src.extractor.clip_pool import load_clip_pool_manifest
from src.generator.collage_builder import build_four_player_collage
from src.generator.explainer_script_generator import generate_explainer_plan, merge_concept_sections
from src.generator.entity_matcher import assign_clips_to_plan
from src.generator.models import ExplainerPlan
from src.generator.plan_defaults import ensure_plan_beats
from src.generator.visual_generator import generate_explainer_visuals
from src.generator.voice_generator import generate_explainer_voiceovers
from src.production_checkpoint import ProductionCheckpoint


def _progress(message: str) -> None:
    print(message, flush=True)


def _collect_existing_images(plan: ExplainerPlan, production_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for section in plan.sections:
        for beat_index, beat in enumerate(section.beats):
            if beat.visual_type == "clip":
                continue
            key = f"{section.id}_{beat_index:02d}"
            path = production_dir / f"beat_{section.id}_{beat_index:02d}.png"
            if path.exists():
                paths[key] = path
    return paths


def _ensure_comparison_collage_on_disk(plan: ExplainerPlan, production_dir: Path, paths: dict[str, Path]) -> None:
    for section in plan.sections:
        if section.section_type != "comparison":
            continue
        collage_path = production_dir / COMPARISON_COLLAGE_FILENAME
        if collage_path.exists():
            paths["comparison_collage"] = collage_path
            return
        panel_paths = [
            paths.get(f"{section.id}_{index:02d}") or production_dir / f"beat_{section.id}_{index:02d}.png"
            for index in range(4)
        ]
        if all(path.exists() for path in panel_paths):
            build_four_player_collage(panel_paths, collage_path)
            paths["comparison_collage"] = collage_path


def run_explainer_production(
    campaign_dir: Path,
    concept_path: Path,
    settings: Settings,
    skip_images: bool = False,
    skip_voice: bool = False,
    skip_assembly: bool = False,
    regenerate_script: bool = False,
    regenerate_images: bool = False,
    regenerate_voice: bool = False,
    regenerate_assembly: bool = False,
    plan_path: Path | None = None,
) -> dict:
    campaign_dir = campaign_dir.resolve()
    concept = load_concept(concept_path)
    clip_pool = load_clip_pool_manifest(campaign_dir)

    production_dir = campaign_dir / "production"
    production_dir.mkdir(parents=True, exist_ok=True)

    saved_plan_path = plan_path or production_dir / "explainer_plan.json"
    checkpoint_path = production_dir / "checkpoint.json"
    checkpoint = ProductionCheckpoint.load(checkpoint_path)

    if checkpoint.script == "completed" and not regenerate_script:
        _progress(f"Resuming — {checkpoint.summary()}")

    if saved_plan_path.exists() and not regenerate_script:
        _progress("Loading saved explainer plan (skip OpenAI script tokens)...")
        plan = ExplainerPlan.model_validate(
            json.loads(saved_plan_path.read_text(encoding="utf-8"))
        )
        checkpoint.mark_script_completed(concept.concept_id)
        checkpoint.save(checkpoint_path)
    else:
        _progress("Generating explainer script via OpenAI...")
        plan = generate_explainer_plan(concept, clip_pool, settings)
        plan = merge_concept_sections(plan, concept)
        saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        checkpoint.mark_script_completed(concept.concept_id)
        checkpoint.save(checkpoint_path)

    if ensure_plan_beats(plan, concept):
        _progress("Filled missing visual beats for comparison/CTA sections...")
        saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    fixed_clips = assign_clips_to_plan(plan, clip_pool)
    if fixed_clips:
        _progress(f"Corrected {fixed_clips} clip assignment(s) to match player source videos...")
        saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    image_paths: dict[str, Path] = {}
    if skip_images:
        _progress("Skipping image generation (--skip-images)...")
        image_paths = _collect_existing_images(plan, production_dir)
        _ensure_comparison_collage_on_disk(plan, production_dir, image_paths)
    else:
        _progress("Generating visuals (reuses saved beats — SerpAPI + OpenAI only for missing)...")

        def on_beat(key: str) -> None:
            checkpoint.mark_image_completed(key)
            checkpoint.save(checkpoint_path)

        image_paths = generate_explainer_visuals(
            plan,
            production_dir,
            settings,
            force_regenerate=regenerate_images,
            on_beat_complete=on_beat,
        )
        _ensure_comparison_collage_on_disk(plan, production_dir, image_paths)

    narration_paths: dict[str, Path] = {}
    if skip_voice:
        _progress("Skipping voice generation (--skip-voice)...")
        for section in plan.narrated_sections():
            path = production_dir / f"narration_{section.id}.mp3"
            if path.exists():
                narration_paths[section.id] = path
    else:
        _progress("Generating voiceovers (reuses saved section MP3s)...")

        def on_voice(section_id: str) -> None:
            checkpoint.mark_voice_completed(section_id)
            checkpoint.save(checkpoint_path)

        narration_paths, voice_id, voice_name = generate_explainer_voiceovers(
            plan,
            production_dir,
            settings,
            force_regenerate=regenerate_voice,
            on_section_complete=on_voice,
        )
        checkpoint.voice_id = voice_id
        checkpoint.voice_name = voice_name
        plan = reconcile_plan_with_narration(plan, narration_paths)
        saved_plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        checkpoint.save(checkpoint_path)

    final_video_path = production_dir / "final_video.mp4"
    if skip_assembly:
        _progress("Skipping assembly (--skip-assembly)...")
    elif (
        final_video_path.exists()
        and not regenerate_assembly
        and checkpoint.assembly == "completed"
    ):
        _progress(f"Reusing final video: {final_video_path}")
    else:
        _progress("Assembling explainer video (may take 15-30 min on CPU)...")
        _ensure_comparison_collage_on_disk(plan, production_dir, image_paths)
        assemble_explainer_video(
            plan=plan,
            campaign_dir=campaign_dir,
            image_paths=image_paths,
            narration_paths=narration_paths,
            output_path=final_video_path,
            settings=settings,
        )
        checkpoint.mark_assembly_completed()
        checkpoint.save(checkpoint_path)

    _progress(f"Done — {checkpoint.summary()}")
    _progress(f"Checkpoint: {checkpoint_path}")

    return {
        "plan_path": saved_plan_path,
        "checkpoint_path": checkpoint_path,
        "production_dir": production_dir,
        "final_video": final_video_path if final_video_path.exists() else None,
        "image_paths": image_paths,
        "narration_paths": narration_paths,
    }
