"""Assemble final video from images, clips, and narration."""

from __future__ import annotations

from pathlib import Path

from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
from moviepy.video.fx.FadeIn import FadeIn

from src.assembler.audio_mixer import apply_background_music
from src.assembler.effects import apply_ken_burns
from src.assembler.subtitles import overlay_caption, word_group_timings, write_srt
from src.config import Settings
from src.extractor.ffmpeg_clipper import extract_clip, probe_duration
from src.generator.models import ProductionPlan, ScriptSegment


def _fit_vertical(clip: VideoFileClip, width: int, height: int) -> VideoFileClip:
    clip = clip.resized(height=height)
    if clip.w > width:
        clip = clip.cropped(x_center=clip.w / 2, width=width, height=height)
    elif clip.w < width:
        clip = clip.resized(width=width)
        if clip.h > height:
            clip = clip.cropped(y_center=clip.h / 2, width=width, height=height)
    return clip


def _image_key(segment: ScriptSegment) -> str:
    if segment.type == "intro":
        return "intro"
    if segment.image_index is None:
        raise ValueError(f"Image segment {segment.order} missing image_index")
    return str(segment.image_index)


def _build_still_segment(
    segment: ScriptSegment,
    image_paths: dict[str, Path],
    narration_paths: dict[int, Path],
    settings: Settings,
    w: int,
    h: int,
    visual_index: int,
    subtitle_entries: list[tuple[float, float, str]],
    timeline_cursor: float,
) -> VideoFileClip:
    key = _image_key(segment)
    if key not in image_paths:
        raise FileNotFoundError(f"Missing image for segment {segment.order} (key={key})")

    narration_path = narration_paths.get(segment.order)
    if narration_path and narration_path.exists():
        audio = AudioFileClip(str(narration_path))
        duration = audio.duration
    else:
        duration = segment.target_duration_sec or settings.intro_duration_sec
        audio = None

    img_clip = ImageClip(str(image_paths[key])).with_duration(duration)
    img_clip = _fit_vertical(img_clip, w, h)
    pan_x = settings.ken_burns_pan if visual_index % 2 == 0 else -settings.ken_burns_pan
    zoom_in = visual_index % 2 == 0
    img_clip = apply_ken_burns(
        img_clip,
        zoom_end=settings.ken_burns_zoom,
        pan_x=pan_x,
        zoom_in=zoom_in,
    )
    if audio:
        img_clip = img_clip.with_audio(audio)

    if settings.enable_captions and segment.narration.strip():
        img_clip = overlay_caption(
            base_clip=img_clip,
            text=segment.narration,
            video_width=w,
            video_height=h,
            font_size=settings.caption_font_size,
            font_path=settings.caption_font_path,
            margin_bottom=settings.caption_margin_bottom,
            caption_width=settings.caption_width,
            intro_style=segment.type == "intro",
            words_per_group=settings.caption_words_per_group,
            min_duration_sec=settings.caption_min_duration_sec,
        )
        group_size = 2 if segment.type == "intro" else settings.caption_words_per_group
        for start, end, group in word_group_timings(
            segment.narration,
            duration,
            words_per_group=group_size,
            min_duration_sec=settings.caption_min_duration_sec,
        ):
            subtitle_entries.append((timeline_cursor + start, timeline_cursor + end, group))

    return img_clip


def _clip_meta_from_manifest(manifest: dict | None, clip_file: str) -> dict | None:
    if not manifest:
        return None
    for clip in manifest.get("clips", []):
        if clip.get("file") == clip_file:
            return clip
    return None


def _load_match_clip(
    run_dir: Path,
    segment: ScriptSegment,
    settings: Settings,
    manifest: dict | None,
    w: int,
    h: int,
) -> VideoFileClip:
    clip_path = run_dir / segment.clip_file
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    target = segment.target_duration_sec or settings.clip_segment_duration
    extracted_duration = probe_duration(clip_path)

    if target > extracted_duration + 0.05:
        meta = _clip_meta_from_manifest(manifest, segment.clip_file)
        source_video = (meta or {}).get("source_video") or (manifest.get("source_video") if manifest else None)
        start_sec = (meta or {}).get("start_sec")
        if source_video and start_sec is not None:
            source_path = Path(source_video)
            if not source_path.is_absolute():
                source_path = run_dir.parent.parent / "input" / source_path.name
            if not source_path.exists():
                source_path = run_dir / source_video
            if source_path.exists():
                recut_path = run_dir / "production" / f"_recut_{segment.clip_file}"
                recut_path.parent.mkdir(parents=True, exist_ok=True)
                extract_clip(source_path, recut_path, float(start_sec), float(start_sec) + target)
                video = VideoFileClip(str(recut_path))
                return _fit_vertical(video, w, h)

    video = VideoFileClip(str(clip_path))
    duration = min(target, video.duration)
    video = video.subclipped(0, duration)
    return _fit_vertical(video, w, h)


def _apply_crossfades(clips: list[VideoFileClip], crossfade_sec: float) -> list[VideoFileClip]:
    if crossfade_sec <= 0 or len(clips) <= 1:
        return clips

    faded: list[VideoFileClip] = [clips[0]]
    for clip in clips[1:]:
        # FadeIn (not CrossFadeIn) — CrossFadeIn breaks on karaoke CompositeVideoClips
        faded.append(clip.with_effects([FadeIn(crossfade_sec)]))
    return faded


def assemble_video(
    plan: ProductionPlan,
    run_dir: Path,
    image_paths: dict[str, Path],
    narration_paths: dict[int, Path],
    output_path: Path,
    settings: Settings,
    manifest: dict | None = None,
) -> Path:
    w, h = settings.video_width, settings.video_height
    video_parts: list[VideoFileClip] = []
    subtitle_entries: list[tuple[float, float, str]] = []
    timeline_cursor = 0.0
    visual_index = 0

    for segment in sorted(plan.segments, key=lambda s: s.order):
        if segment.type in ("intro", "image"):
            img_clip = _build_still_segment(
                segment=segment,
                image_paths=image_paths,
                narration_paths=narration_paths,
                settings=settings,
                w=w,
                h=h,
                visual_index=visual_index,
                subtitle_entries=subtitle_entries,
                timeline_cursor=timeline_cursor,
            )
            video_parts.append(img_clip)
            timeline_cursor += img_clip.duration or 0.0
            visual_index += 1

        elif segment.type == "clip":
            video = _load_match_clip(run_dir, segment, settings, manifest, w, h)
            video_parts.append(video)
            timeline_cursor += video.duration or 0.0

    if not video_parts:
        raise RuntimeError("No video segments to assemble.")

    if subtitle_entries:
        write_srt(subtitle_entries, output_path.parent / "subtitles.srt")

    crossfade = settings.crossfade_duration
    composed_parts = _apply_crossfades(video_parts, crossfade)
    if crossfade > 0 and len(composed_parts) > 1:
        final = concatenate_videoclips(composed_parts, method="compose", padding=-crossfade)
    else:
        final = concatenate_videoclips(composed_parts, method="compose")

    bg_music: AudioFileClip | None = None
    if settings.bg_music_path:
        final, bg_music = apply_background_music(
            video=final,
            music_path=settings.bg_music_path,
            volume=settings.bg_music_volume,
            fade_in=settings.bg_music_fade_in,
            fade_out=settings.bg_music_fade_out,
        )

    final.write_videofile(
        str(output_path),
        fps=settings.video_fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(output_path.parent / "temp-audio.m4a"),
        remove_temp=True,
        logger="bar",
    )

    for clip in video_parts:
        clip.close()
    if bg_music:
        bg_music.close()
    final.close()

    return output_path
