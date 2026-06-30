"""Compose multi-player comparison collages from beat images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _cover_resize(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize and center-crop to fill target dimensions."""
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def build_four_player_collage(
    image_paths: list[Path],
    output_path: Path,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    gutter: int = 6,
) -> Path:
    """
    2x2 grid collage for portrait video (four players, one per cell).
    """
    paths = [path for path in image_paths if path.exists()][:4]
    if len(paths) < 4:
        raise ValueError(f"Need 4 images for collage, got {len(paths)}")

    cols, rows = 2, 2
    cell_w = (canvas_w - gutter * (cols - 1)) // cols
    cell_h = (canvas_h - gutter * (rows - 1)) // rows
    canvas = Image.new("RGB", (canvas_w, canvas_h), (12, 14, 20))

    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        tile = _cover_resize(image, cell_w, cell_h)
        col = index % cols
        row = index // cols
        x = col * (cell_w + gutter)
        y = row * (cell_h + gutter)
        canvas.paste(tile, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return output_path
