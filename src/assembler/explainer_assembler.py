"""Assemble explainer videos from beats, clips, and section narration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
from moviepy.video.fx.FadeIn import FadeIn

from src.assembler.audio_mixer import apply_background_music
from src.assembler.effects import apply_ken_burns
from src.assembler.subtitles import overlay_karaoke_captions, write_srt
from src.assembler.video_assembler import _fit_vertical
from src.config import Settings
from src.extractor.ffmpeg_clipper import probe_duration
from src.generator.collage_builder import build_four_player_collage
from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat

COMPARISON_COLLAGE_KEY = "comparison_collage"
COMPARISON_COLLAGE_FILENAME = "beat_comparison_collage.png"


def _beat_duration_cap(beat: VisualBeat, settings: Settings, section_type: str) -> float:
    if beat.visual_type == "clip":
        return 9999.0
    if beat.visual_type == "ai_image":
        if section_type == "hook":
            return settings.hook_beat_sec
        return settings.max_ai_beat_sec
    return settings.max_still_beat_sec


def _plan_beat_timeline(
    beats: list[VisualBeat],
    target_duration: float,
    settings: Settings,
    section_type: str,
) -> list[tuple[VisualBeat, int, float]]:
    """Return (beat, source_beat_index for image lookup, duration) per cut."""
    if not beats:
        return []

    caps = [_beat_duration_cap(beat, settings, section_type) for beat in beats]
    base = [
        min(beat.duration_sec if beat.duration_sec > 0 else caps[index], caps[index])
        for index, beat in enumerate(beats)
    ]
    clip_indices = [index for index, beat in enumerate(beats) if beat.visual_type == "clip"]
    still_indices = [index for index in range(len(beats)) if index not in clip_indices]

    if section_type == "hook" or not clip_indices:
        timeline: list[tuple[VisualBeat, int, float]] = []
        cursor = 0.0
        cycle = 0
        while cursor < target_duration - 0.05:
            index = cycle % len(beats)
            duration = min(base[index], target_duration - cursor)
            duration = max(0.35, duration)
            timeline.append((beats[index], index, duration))
            cursor += duration
            cycle += 1
        return timeline

    still_total = sum(base[index] for index in still_indices)
    clip_floor = sum(base[index] for index in clip_indices)
    clip_budget = max(clip_floor, target_duration - still_total)

    durations = list(base)
    if clip_indices and clip_floor > 0:
        clip_scale = clip_budget / clip_floor
        for index in clip_indices:
            durations[index] = base[index] * clip_scale

    total = sum(durations)
    if total > 0 and abs(total - target_duration) > 0.05:
        scale = target_duration / total
        durations = [duration * scale for duration in durations]

    drift = target_duration - sum(durations)
    if clip_indices and abs(drift) > 0.01:
        durations[clip_indices[-1]] = max(0.5, durations[clip_indices[-1]] + drift)

    return [(beats[index], index, durations[index]) for index in range(len(beats))]


def _comparison_collage_path(image_paths: dict[str, Path], production_dir: Path) -> Path | None:
    path = image_paths.get(COMPARISON_COLLAGE_KEY)
    if path and path.exists():
        return path
    fallback = production_dir / COMPARISON_COLLAGE_FILENAME
    if fallback.exists():
        return fallback
    return None


def _ensure_comparison_collage(
    section: ExplainerSection,
    image_paths: dict[str, Path],
    production_dir: Path,
) -> Path | None:
    existing = _comparison_collage_path(image_paths, production_dir)
    if existing:
        return existing

    panel_paths: list[Path] = []
    for beat_index in range(4):
        key = f"{section.id}_{beat_index:02d}"
        path = image_paths.get(key) or production_dir / f"beat_{section.id}_{beat_index:02d}.png"
        if path.exists():
            panel_paths.append(path)

    if len(panel_paths) < 4:
        return None

    out_path = production_dir / COMPARISON_COLLAGE_FILENAME
    build_four_player_collage(panel_paths, out_path)
    image_paths[COMPARISON_COLLAGE_KEY] = out_path
    return out_path


def _build_image_beat(
    image_path: Path,
    duration: float,
    settings: Settings,
    w: int,
    h: int,
    visual_index: int,
) -> VideoFileClip:
    img_clip = ImageClip(str(image_path)).with_duration(duration)
    img_clip = _fit_vertical(img_clip, w, h)
    pan_x = settings.ken_burns_pan if visual_index % 2 == 0 else -settings.ken_burns_pan
    zoom_in = visual_index % 2 == 0
    return apply_ken_burns(
        img_clip,
        zoom_end=settings.explainer_ken_burns_zoom,
        pan_x=pan_x,
        zoom_in=zoom_in,
    )


def _build_clip_beat(
    clip_path: Path,
    duration: float,
    w: int,
    h: int,
) -> VideoFileClip:
    video = VideoFileClip(str(clip_path))
    use_duration = min(duration, video.duration or duration)
    video = video.subclipped(0, use_duration)
    return _fit_vertical(video, w, h)


def _apply_keyword_caption(
    clip: VideoFileClip,
    text: str,
    settings: Settings,
    w: int,
    h: int,
) -> VideoFileClip:
    if not text.strip() or not settings.enable_captions:
        return clip
    if settings.caption_mode != "keyword":
        return clip
    return overlay_karaoke_captions(
        base_clip=clip,
        text=text,
        video_width=w,
        video_height=h,
        font_size=settings.caption_font_size,
        font_path=settings.caption_font_path,
        words_per_group=len(text.split()),
        min_duration_sec=min(clip.duration or 1.0, settings.caption_min_duration_sec),
        keyword_style=True,
        margin_bottom=settings.caption_margin_bottom,
    )


def _apply_crossfades(clips: list[VideoFileClip], crossfade_sec: float) -> list[VideoFileClip]:
    if crossfade_sec <= 0 or len(clips) <= 1:
        return clips
    faded: list[VideoFileClip] = [clips[0]]
    for clip in clips[1:]:
        faded.append(clip.with_effects([FadeIn(crossfade_sec)]))
    return faded


def _build_placeholder_beat(
    duration: float,
    w: int,
    h: int,
    settings: Settings,
    visual_index: int,
    label: str = "",
) -> VideoFileClip:
    """Solid fallback frame when no beat image exists on disk."""
    rgb = (18, 22, 32)
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :] = rgb
    clip = ImageClip(frame).with_duration(max(0.5, duration))
    clip = _fit_vertical(clip, w, h)
    pan_x = settings.ken_burns_pan if visual_index % 2 == 0 else -settings.ken_burns_pan
    return apply_ken_burns(
        clip,
        zoom_end=settings.explainer_ken_burns_zoom,
        pan_x=pan_x,
        zoom_in=visual_index % 2 == 0,
    )


def _build_section(
    section: ExplainerSection,
    narration_path: Path | None,
    image_paths: dict[str, Path],
    clip_pool_dir: Path,
    settings: Settings,
    w: int,
    h: int,
    visual_index: int,
    subtitle_entries: list[tuple[float, float, str]],
    timeline_cursor: float,
    production_dir: Path,
) -> tuple[VideoFileClip, int]:
    has_narration = narration_path and narration_path.exists() and section.narration.strip()
    if has_narration:
        audio = AudioFileClip(str(narration_path))
        section_duration = audio.duration or section.target_duration_sec
    else:
        audio = None
        section_duration = section.target_duration_sec or sum(b.duration_sec for b in section.beats)

    visual_beats = section.beats
    if not visual_beats:
        section_duration = section_duration or 3.0
        visual_beats = [
            VisualBeat(
                duration_sec=section_duration,
                visual_type="web_image",
                image_search_query=section.entity_name or section.keyword,
            )
        ]

    if section.section_type == "comparison":
        collage_path = _ensure_comparison_collage(section, image_paths, production_dir)
        if collage_path:
            beat_clip = _build_image_beat(
                collage_path, section_duration, settings, w, h, visual_index
            )
            visual_index += 1
            highlight = section.keyword or "FOUR DIFFERENT PRESSURES"
            if highlight:
                beat_clip = _apply_keyword_caption(beat_clip, highlight, settings, w, h)
                if settings.enable_captions:
                    subtitle_entries.append(
                        (timeline_cursor, timeline_cursor + section_duration, highlight.upper())
                    )
            section_video = beat_clip
            if audio:
                section_video = section_video.with_audio(audio)
            return section_video, visual_index

    beat_timeline = _plan_beat_timeline(
        visual_beats, section_duration, settings, section.section_type
    )
    beat_clips: list[VideoFileClip] = []

    crossfade = (
        settings.hook_crossfade_sec
        if section.section_type == "hook"
        else settings.explainer_crossfade_sec
    )

    for timeline_index, (beat, source_index, duration) in enumerate(beat_timeline):
        beat_clip: VideoFileClip | None = None
        if beat.visual_type == "clip" and beat.clip_file:
            clip_path = clip_pool_dir / beat.clip_file
            if clip_path.exists():
                beat_clip = _build_clip_beat(clip_path, duration, w, h)
            else:
                key = f"{section.id}_{source_index:02d}"
                img_path = image_paths.get(key)
                if img_path and img_path.exists():
                    beat_clip = _build_image_beat(img_path, duration, settings, w, h, visual_index)
                    visual_index += 1
        else:
            key = f"{section.id}_{source_index:02d}"
            img_path = image_paths.get(key)
            if img_path and img_path.exists():
                beat_clip = _build_image_beat(img_path, duration, settings, w, h, visual_index)
                visual_index += 1

        if beat_clip is None:
            label = beat.caption_highlight or section.keyword or section.id
            print(
                f"  Placeholder visual for {section.id} beat {timeline_index} (no image on disk)",
                flush=True,
            )
            beat_clip = _build_placeholder_beat(
                duration, w, h, settings, visual_index, label=label
            )
            visual_index += 1

        highlight = beat.caption_highlight or (
            section.keyword if timeline_index == 0 and section.keyword else ""
        )
        if highlight:
            beat_clip = _apply_keyword_caption(beat_clip, highlight, settings, w, h)
            if settings.enable_captions:
                subtitle_entries.append(
                    (timeline_cursor, timeline_cursor + duration, highlight.upper())
                )

        beat_clips.append(beat_clip)
        timeline_cursor += duration

    if not beat_clips:
        print(f"  No beat images for {section.id} — using full-section placeholder", flush=True)
        beat_clips.append(
            _build_placeholder_beat(
                section_duration,
                w,
                h,
                settings,
                visual_index,
                label=section.keyword or section.id,
            )
        )

    composed_beats = _apply_crossfades(beat_clips, crossfade)
    if crossfade > 0 and len(composed_beats) > 1:
        section_video = concatenate_videoclips(
            composed_beats, method="compose", padding=-crossfade
        )
    else:
        section_video = concatenate_videoclips(composed_beats, method="compose")

    if audio:
        section_video = section_video.with_audio(audio)

    return section_video, visual_index


def assemble_explainer_video(
    plan: ExplainerPlan,
    campaign_dir: Path,
    image_paths: dict[str, Path],
    narration_paths: dict[str, Path],
    output_path: Path,
    settings: Settings,
) -> Path:
    w, h = settings.video_width, settings.video_height
    clip_pool_dir = campaign_dir / "clip_pool"
    production_dir = campaign_dir / "production"
    section_parts: list[VideoFileClip] = []
    subtitle_entries: list[tuple[float, float, str]] = []
    timeline_cursor = 0.0
    visual_index = 0

    for section in plan.sections:
        if not section.beats and not section.narration.strip():
            continue
        narration_path = narration_paths.get(section.id)
        section_video, visual_index = _build_section(
            section=section,
            narration_path=narration_path,
            image_paths=image_paths,
            clip_pool_dir=clip_pool_dir,
            settings=settings,
            w=w,
            h=h,
            visual_index=visual_index,
            subtitle_entries=subtitle_entries,
            timeline_cursor=timeline_cursor,
            production_dir=production_dir,
        )
        section_parts.append(section_video)
        timeline_cursor += section_video.duration or 0.0

    if not section_parts:
        raise RuntimeError("No sections to assemble.")

    if subtitle_entries:
        write_srt(subtitle_entries, output_path.parent / "subtitles.srt")

    final = concatenate_videoclips(section_parts, method="compose")

    bg_music: AudioFileClip | None = None
    if settings.bg_music_path:
        final, bg_music = apply_background_music(
            video=final,
            music_path=settings.bg_music_path,
            volume=settings.bg_music_volume,
            fade_in=settings.bg_music_fade_in,
            fade_out=settings.bg_music_fade_out,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=settings.video_fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(output_path.parent / "temp-audio.m4a"),
        remove_temp=True,
        logger="bar",
    )

    for clip in section_parts:
        clip.close()
    if bg_music:
        bg_music.close()
    final.close()

    return output_path


def reconcile_plan_with_narration(
    plan: ExplainerPlan,
    narration_paths: dict[str, Path],
) -> ExplainerPlan:
    """Update section target durations from actual narration audio length."""
    for section in plan.sections:
        path = narration_paths.get(section.id)
        if path and path.exists():
            section.target_duration_sec = probe_duration(path)
    return plan
