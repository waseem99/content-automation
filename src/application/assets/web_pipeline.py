from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from src.application.assets.models import AssetHandle
from src.application.assets.pipeline import register_web_image_pair
from src.application.assets.registry import AssetRegistryService


@dataclass(frozen=True, slots=True)
class RegisteredWebImage:
    source: AssetHandle
    derivative: AssetHandle
    source_path: Path
    normalized_path: Path
    width: int
    height: int


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


def persist_and_register_web_image(
    *,
    content: bytes,
    out_path: Path,
    minimum_width: int,
    registry: AssetRegistryService,
    metadata: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> RegisteredWebImage:
    source_path, normalized_path, width, height = persist_original_and_normalized(
        content=content,
        out_path=out_path,
        minimum_width=minimum_width,
    )
    source, derivative = register_web_image_pair(
        original_path=source_path,
        normalized_path=normalized_path,
        registry=registry,
        metadata={"width": width, "height": height, **(metadata or {})},
        created_by=created_by,
    )
    return RegisteredWebImage(
        source=source,
        derivative=derivative,
        source_path=source_path,
        normalized_path=normalized_path,
        width=width,
        height=height,
    )
