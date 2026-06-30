"""Background music mixing helpers."""

from __future__ import annotations

from pathlib import Path

from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, afx


def apply_background_music(
    video: VideoFileClip,
    music_path: Path,
    volume: float = 0.12,
    fade_in: float = 0.5,
    fade_out: float = 1.5,
) -> tuple[VideoFileClip, AudioFileClip]:
    """Trim music to video length, lower volume, fade, and mix under existing audio."""
    if not music_path.exists():
        raise FileNotFoundError(f"Background music not found: {music_path}")

    duration = video.duration
    music = AudioFileClip(str(music_path))
    music = music.subclipped(0, min(duration, music.duration))

    if volume != 1.0:
        music = music.with_volume_scaled(volume)

    effects = []
    if fade_in > 0:
        effects.append(afx.AudioFadeIn(fade_in))
    if fade_out > 0:
        effects.append(afx.AudioFadeOut(fade_out))
    if effects:
        music = music.with_effects(effects)

    if video.audio:
        mixed = CompositeAudioClip([video.audio, music])
    else:
        mixed = music

    return video.with_audio(mixed), music
