"""Visual effects: Ken Burns zoom on still images."""

from __future__ import annotations

import numpy as np
from PIL import Image
from moviepy import VideoClip


def apply_ken_burns(
    clip: VideoClip,
    zoom_end: float = 1.30,
    pan_x: float = 0.35,
    zoom_in: bool = True,
) -> VideoClip:
    """Visible slow zoom + pan on a still image clip."""
    width, height = clip.size
    duration = clip.duration or 1.0
    zoom_start = 1.0 if zoom_in else zoom_end
    zoom_finish = zoom_end if zoom_in else 1.0

    def effect(get_frame, t):
        progress = min(1.0, max(0.0, t / duration))
        eased = progress * progress * (3 - 2 * progress)  # smoothstep
        scale = zoom_start + (zoom_finish - zoom_start) * eased
        frame = get_frame(t)
        image = Image.fromarray(frame)
        new_w = max(width + 1, int(width * scale))
        new_h = max(height + 1, int(height * scale))
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        max_left = max(0, new_w - width)
        max_top = max(0, new_h - height)
        pan_shift = pan_x * eased
        left = int(max_left * (0.5 + pan_shift))
        top = int(max_top * 0.5)
        image = image.crop((left, top, left + width, top + height))
        return np.array(image)

    return clip.transform(effect)
