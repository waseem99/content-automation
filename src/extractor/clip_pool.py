"""Multi-source clip extraction and pooling for explainer campaigns."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.analyzer.audio_analyzer import detect_energy_spikes
from src.analyzer.scene_detector import detect_scenes
from src.analyzer.topic_matcher import score_transcript_segments
from src.analyzer.transcriber import transcribe_audio
from src.concepts.loader import ConceptDefinition
from src.config import Settings
from src.generator.entity_matcher import resolve_video_entity
from src.extractor.ffmpeg_clipper import (
    extract_audio_wav,
    extract_clips,
    format_timestamp,
    probe_duration,
    slugify_label,
)
from src.ranker.moment_ranker import rank_moments


def _slugify_entity(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "entity"


def _topic_for_video(video_path: Path, concept: ConceptDefinition, video_index: int) -> str:
    resolved = resolve_video_entity(video_path, concept)
    if resolved:
        return resolved[1]
    topics = concept.extraction.topics
    if not topics:
        return concept.title
    if video_index < len(topics):
        return topics[video_index]
    return topics[video_index % len(topics)]


def _entity_for_topic(topic: str, concept: ConceptDefinition, video_path: Path | None = None) -> str:
    if video_path is not None:
        resolved = resolve_video_entity(video_path, concept)
        if resolved:
            return resolved[0]
    topic_lower = topic.lower()
    for section in concept.entity_sections():
        if section.entity_name.lower() in topic_lower:
            return section.entity_name
    for section in concept.entity_sections():
        parts = section.entity_name.lower().split()
        if parts and parts[-1] in topic_lower:
            return section.entity_name
    return ""


def extract_single_video(
    video_path: Path,
    topic: str,
    entity: str,
    output_dir: Path,
    clip_pool_dir: Path,
    settings: Settings,
    max_duration: float | None = None,
) -> list[dict]:
    """Extract ranked clips from one video; copy into clip_pool_dir and return metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_pool_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / "analysis_audio.wav"
    extract_audio_wav(video_path, wav_path, max_duration=max_duration)

    full_duration = probe_duration(video_path)
    analyze_duration = min(full_duration, max_duration) if max_duration else full_duration

    scenes = detect_scenes(video_path, threshold=settings.scene_threshold)
    if max_duration is not None:
        scenes = [s for s in scenes if s.time_sec <= max_duration]

    energy_spikes = detect_energy_spikes(
        wav_path,
        window_sec=settings.energy_window_sec,
        top_percentile=settings.energy_top_percentile,
    )

    transcript = transcribe_audio(
        wav_path,
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    transcript_hits = score_transcript_segments(transcript, topic)

    local_settings = settings.model_copy()
    local_settings.clip_count = settings.clip_count
    local_settings.clip_duration = settings.clip_duration

    windows = rank_moments(
        scenes=scenes,
        energy_spikes=energy_spikes,
        transcript_hits=transcript_hits,
        video_duration=analyze_duration,
        settings=local_settings,
    )
    if not windows:
        return []

    clip_paths = extract_clips(video_path, output_dir, windows)
    clips: list[dict] = []
    entity_slug = _slugify_entity(entity) if entity else "general"

    for index, (window, clip_path) in enumerate(zip(windows, clip_paths), start=1):
        dest_name = f"{entity_slug}_clip_{index:02d}_{slugify_label(window.label)}.mp4"
        dest_path = clip_pool_dir / dest_name
        if clip_path != dest_path:
            shutil.copy2(clip_path, dest_path)
        clips.append(
            {
                "file": dest_name,
                "entity": entity,
                "topic": topic,
                "source_video": str(video_path.resolve()),
                "start": format_timestamp(window.start),
                "end": format_timestamp(window.end),
                "start_sec": round(window.start, 3),
                "end_sec": round(window.end, 3),
                "score": round(window.score, 4),
                "label": window.label,
                "source_text": window.source_text,
            }
        )
    return clips


def build_clip_pool(
    videos: list[Path],
    concept: ConceptDefinition,
    campaign_dir: Path,
    settings: Settings,
    max_duration: float | None = None,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Extract clips from multiple videos into campaign_dir/clip_pool/."""
    log = progress or (lambda msg: print(msg, flush=True))
    clip_pool_dir = campaign_dir / "clip_pool"
    extractions_dir = campaign_dir / "extractions"
    clip_pool_dir.mkdir(parents=True, exist_ok=True)
    extractions_dir.mkdir(parents=True, exist_ok=True)

    pool_settings = settings.model_copy()
    pool_settings.clip_count = concept.extraction.clips_per_video
    pool_settings.clip_duration = concept.extraction.clip_duration

    all_clips: list[dict] = []
    for video_index, video_path in enumerate(videos):
        if not video_path.exists():
            log(f"Skipping missing video: {video_path}")
            continue
        topic = _topic_for_video(video_path, concept, video_index)
        entity = _entity_for_topic(topic, concept, video_path)
        if not entity:
            log(f"Skipping unmatched video (rename file to include player name): {video_path.name}")
            continue
        log(f"Extracting [{video_index + 1}/{len(videos)}]: {video_path.name} — {topic}")
        run_dir = extractions_dir / f"{video_path.stem}_{video_index:02d}"
        clips = extract_single_video(
            video_path=video_path,
            topic=topic,
            entity=entity,
            output_dir=run_dir,
            clip_pool_dir=clip_pool_dir,
            settings=pool_settings,
            max_duration=max_duration,
        )
        all_clips.extend(clips)
        log(f"  → {len(clips)} clips")

    manifest = {
        "concept_id": concept.concept_id,
        "title": concept.title,
        "created_at": datetime.now().isoformat(),
        "source_videos": [str(v.resolve()) for v in videos if v.exists()],
        "clips": all_clips,
    }
    manifest_path = clip_pool_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"Clip pool: {len(all_clips)} clips → {manifest_path}")
    return manifest_path


def load_clip_pool_manifest(campaign_dir: Path) -> dict:
    manifest_path = campaign_dir / "clip_pool" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Clip pool manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))
