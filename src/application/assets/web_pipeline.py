from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image


def persist_original_and_normalized(
    *,
    content: bytes,
    out_path: Path,
    minimum_width: int,
) -> tuple[Path, Path, int, int]:
    image = Image.open(BytesIO(content))
    image.load()
    width, height = image.size
    if width < minimum_width:
        raise ValueError(f"Image too small: {width}x{height}")

    format_name = (image.format or "bin").lower()
    extension = {
        "jpeg": "jpg",
        "jpg": "jpg",
        "png": "png",
        "webp": "webp",
        "gif": "gif",
    }.get(format_name, "bin")
    source_path = out_path.with_name(f"{out_path.stem}_source.{extension}")
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(image, mask=image.getchannel("A"))
        image = background

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG")
    return source_path, out_path, width, height
