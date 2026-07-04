from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import CompositeVideoClip, ImageClip, VideoClip


DEFAULT_WATERMARK = "PREVIEW - NOT FOR PUBLICATION"


def apply_preview_watermark(
    video: VideoClip,
    *,
    text: str = DEFAULT_WATERMARK,
) -> CompositeVideoClip:
    width = int(video.w)
    height = max(96, int(video.h * 0.09))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 150))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(18, height // 4))
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    draw.text(
        ((width - text_width) / 2, (height - text_height) / 2),
        text,
        font=font,
        fill=(255, 255, 255, 235),
    )
    overlay = (
        ImageClip(np.array(image))
        .with_duration(video.duration)
        .with_position(("center", "center"))
    )
    return CompositeVideoClip([video, overlay], size=(int(video.w), int(video.h)))


def write_preview_metadata(output_path: Path, *, watermark_text: str) -> Path:
    import json

    metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "NOT_FOR_PUBLICATION": True,
                "publication_eligible": False,
                "watermark_text": watermark_text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return metadata_path
