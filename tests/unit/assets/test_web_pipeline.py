from __future__ import annotations

from io import BytesIO

from PIL import Image

from src.application.assets.web_pipeline import persist_original_and_normalized


def test_original_response_bytes_are_preserved_before_normalization(tmp_path) -> None:
    image = Image.new("RGB", (800, 450), (20, 40, 60))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=83)
    original_bytes = buffer.getvalue()
    normalized = tmp_path / "image_01.png"

    source_path, normalized_path, width, height = persist_original_and_normalized(
        content=original_bytes,
        out_path=normalized,
        minimum_width=600,
    )

    assert source_path.name == "image_01_source.jpg"
    assert source_path.read_bytes() == original_bytes
    assert normalized_path == normalized
    assert (width, height) == (800, 450)
    with Image.open(normalized_path) as generated:
        assert generated.format == "PNG"
        assert generated.size == (800, 450)
