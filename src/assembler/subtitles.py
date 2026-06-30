"""Caption overlays: word-by-word karaoke style + SRT export."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from moviepy import CompositeVideoClip, TextClip, VideoClip
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut

DEFAULT_WINDOWS_FONT = Path("C:/Windows/Fonts/arialbd.ttf")
LINUX_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
]


def resolve_caption_font(custom_font: Path | None = None) -> str | None:
    if custom_font and custom_font.exists():
        return str(custom_font)
    if DEFAULT_WINDOWS_FONT.exists():
        return str(DEFAULT_WINDOWS_FONT)
    for candidate in LINUX_FONT_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def split_word_groups(text: str, words_per_group: int = 1) -> list[str]:
    words = re.findall(r"\S+", text.strip())
    if not words:
        return []
    groups: list[str] = []
    for index in range(0, len(words), words_per_group):
        groups.append(" ".join(words[index : index + words_per_group]))
    return groups


def wrap_caption_text(text: str, width: int = 32) -> str:
    cleaned = " ".join(text.split())
    return "\n".join(textwrap.wrap(cleaned, width=width)) or cleaned


def word_group_timings(
    text: str,
    total_duration: float,
    words_per_group: int = 1,
    min_duration_sec: float = 0.45,
) -> list[tuple[float, float, str]]:
    groups = split_word_groups(text, words_per_group=words_per_group)
    if not groups:
        return []

    min_total = min_duration_sec * len(groups)
    if min_total >= total_duration:
        slot = total_duration / len(groups)
        return [(index * slot, (index + 1) * slot, group) for index, group in enumerate(groups)]

    remaining = total_duration - min_total
    extra_per_group = remaining / len(groups)
    timings: list[tuple[float, float, str]] = []
    cursor = 0.0
    for group in groups:
        slot = min_duration_sec + extra_per_group
        timings.append((cursor, cursor + slot, group))
        cursor += slot
    return timings


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(entries: list[tuple[float, float, str]], output_path: Path) -> Path:
    lines: list[str] = []
    for index, (start, end, text) in enumerate(entries, start=1):
        lines.append(str(index))
        lines.append(f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}")
        lines.append(text.upper())
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _caption_position(y_position: str | int | tuple[str | int, str | int]) -> str | tuple[str | int, str | int]:
    if isinstance(y_position, int):
        return ("center", y_position)
    return y_position


def _make_caption_clip(
    text: str,
    duration: float,
    font_size: int,
    font_path: Path | None,
    y_position: str | int | tuple[str | int, str | int],
    stroke_width: int = 5,
) -> TextClip:
    font = resolve_caption_font(font_path)
    fade = min(0.12, duration / 4)
    clip = TextClip(
        text=text.upper(),
        font=font,
        font_size=font_size,
        color="white",
        stroke_color="black",
        stroke_width=stroke_width,
        method="label",
        text_align="center",
        horizontal_align="center",
    ).with_duration(duration)
    if fade > 0.02:
        clip = clip.with_effects([FadeIn(fade), FadeOut(fade)])
    return clip.with_position(_caption_position(y_position))


def _keyword_caption_y(video_height: int, caption_height: int, margin_bottom: int) -> int:
    """Place keyword text in the upper-middle safe zone (avoids bottom clipping)."""
    preferred = int(video_height * 0.38)
    max_y = video_height - margin_bottom - caption_height
    return max(80, min(preferred, max_y))


def overlay_karaoke_captions(
    base_clip: VideoClip,
    text: str,
    video_width: int,
    video_height: int,
    font_size: int = 58,
    font_path: Path | None = None,
    words_per_group: int = 1,
    min_duration_sec: float = 0.45,
    intro_style: bool = False,
    keyword_style: bool = False,
    margin_bottom: int = 180,
) -> VideoClip:
    if not text.strip():
        return base_clip

    duration = base_clip.duration or 1.0
    group_size = 2 if intro_style else words_per_group
    timings = word_group_timings(
        text,
        duration,
        words_per_group=group_size,
        min_duration_sec=min_duration_sec,
    )
    if not timings:
        return base_clip

    if keyword_style:
        size = font_size + 6
        stroke = 4
    else:
        size = font_size + (16 if intro_style else 0)
        stroke = 5

    layers: list[VideoClip] = [base_clip]
    for start, end, group in timings:
        caption = TextClip(
            text=group.upper(),
            font=resolve_caption_font(font_path),
            font_size=size,
            color="white",
            stroke_color="black",
            stroke_width=stroke,
            method="label",
            text_align="center",
            horizontal_align="center",
        ).with_duration(end - start)
        fade = min(0.12, (end - start) / 4)
        if fade > 0.02:
            caption = caption.with_effects([FadeIn(fade), FadeOut(fade)])

        if keyword_style:
            y = _keyword_caption_y(video_height, caption.h, margin_bottom)
            y_pos: str | int | tuple[str | int, str | int] = ("center", y)
        elif intro_style:
            y_pos = "center"
        else:
            y_pos = int(video_height * 0.68)

        caption = caption.with_position(_caption_position(y_pos)).with_start(start)
        layers.append(caption)

    return CompositeVideoClip(layers, size=(video_width, video_height))


def overlay_caption(
    base_clip: VideoClip,
    text: str,
    video_width: int,
    video_height: int,
    font_size: int = 58,
    font_path: Path | None = None,
    margin_bottom: int = 140,
    caption_width: int = 900,
    intro_style: bool = False,
    words_per_group: int = 1,
    min_duration_sec: float = 0.45,
) -> VideoClip:
    if not text.strip():
        return base_clip

    return overlay_karaoke_captions(
        base_clip=base_clip,
        text=text,
        video_width=video_width,
        video_height=video_height,
        font_size=font_size,
        font_path=font_path,
        words_per_group=words_per_group,
        min_duration_sec=min_duration_sec,
        intro_style=intro_style,
    )
