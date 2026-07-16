from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat
from pydantic import BaseModel, ConfigDict, Field

from .acquisition import sha256_path
from .models import RightsDeclaration

SUPPORTED_IMAGES = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
CTA_TERMS = {
    "book now",
    "buy now",
    "follow",
    "learn more",
    "link in bio",
    "order now",
    "shop now",
    "subscribe",
    "swipe",
    "visit",
}


class ImageRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    REUSED = "reused"


class EvidenceKind(StrEnum):
    MEASURED = "measured"
    EXTRACTED = "extracted"
    MODEL_OBSERVATION = "model_observation"
    UNAVAILABLE = "unavailable"


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class TextRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    confidence: float = Field(ge=0, le=1)
    box: BoundingBox


class PaletteColor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hex: str
    share: float = Field(ge=0, le=1)


class ImageMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    aspect_ratio: float = Field(gt=0)
    orientation: str
    mode: str
    format: str
    size_bytes: int = Field(ge=0)
    sha256: str
    brightness: float = Field(ge=0, le=255)
    contrast: float = Field(ge=0)
    saturation: float = Field(ge=0, le=255)
    entropy: float = Field(ge=0)
    edge_density: float = Field(ge=0, le=1)
    visual_center: tuple[float, float]
    dominant_palette: list[PaletteColor]


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    provider: str
    source_type: EvidenceKind
    text: str = ""
    mean_confidence: float | None = Field(default=None, ge=0, le=1)
    regions: list[TextRegion] = Field(default_factory=list)
    text_coverage: float = Field(default=0, ge=0, le=1)
    hierarchy: dict[str, int] = Field(default_factory=dict)
    cta_candidate: bool = False
    cta_evidence: list[str] = Field(default_factory=list)


class ModelObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "unavailable"
    provider: str = "none"
    source_type: EvidenceKind = EvidenceKind.UNAVAILABLE
    subjects: list[str] = Field(default_factory=list)
    layout_summary: str | None = None
    visual_hierarchy: list[str] = Field(default_factory=list)
    narrative_role: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ImageSlide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    asset_name: str
    stored_path: str
    sequence_role: str
    measurements: ImageMeasurement
    ocr: OCRResult
    observation: ModelObservation


class ImageFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    asset_name: str
    error_type: str
    error: str
    fallback_action: str = "Provide a readable authorized local image export."


class CarouselMapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    role: str
    evidence: list[str]
    confidence: float = Field(ge=0, le=1)


class ImageReferenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.image_reference.v1"
    reference_id: str
    title: str
    status: ImageRunStatus
    rights_declaration: RightsDeclaration
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_digest: str
    media_kind: str
    attempted_count: int
    slide_count: int
    slides: list[ImageSlide]
    failures: list[ImageFailure] = Field(default_factory=list)
    carousel_map: list[CarouselMapEntry]
    contact_sheet: str | None
    limitations: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    source_text_must_not_be_reused_verbatim: bool = True
    source_media_must_not_enter_generated_content: bool = True
    automatic_publication: bool = False


class ImageObserver(Protocol):
    name: str

    def observe(self, image_path: Path, *, index: int, total: int) -> ModelObservation: ...


class OllamaImageObserver:
    name = "ollama-image-observer"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
    ) -> None:
        self.model = model
        self.endpoint = endpoint

    def observe(self, image_path: Path, *, index: int, total: int) -> ModelObservation:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = (
            f"Analyze slide {index} of {total} for internal reference research. Return JSON with "
            "subjects (generic descriptions only), layout_summary, visual_hierarchy (list), "
            "narrative_role, and confidence. Do not identify private people. Distinguish observed "
            "content from intent and do not recommend copying wording, artwork, or composition."
        )
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(
                {
                    "model": self.model,
                    "stream": False,
                    "format": "json",
                    "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw.get("message", {}).get("content", "{}")
            payload = json.loads(content) if isinstance(content, str) else content
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Local image observation failed: {type(exc).__name__}") from exc
        subjects = payload.get("subjects") or []
        hierarchy = payload.get("visual_hierarchy") or []
        try:
            confidence = min(1.0, max(0.0, float(payload.get("confidence", 0.65))))
        except (TypeError, ValueError):
            confidence = 0.65
        return ModelObservation(
            status="succeeded",
            provider=f"{self.name}:{self.model}",
            source_type=EvidenceKind.MODEL_OBSERVATION,
            subjects=[str(item) for item in subjects if str(item).strip()][:10],
            layout_summary=str(payload.get("layout_summary") or "") or None,
            visual_hierarchy=[str(item) for item in hierarchy if str(item).strip()][:10],
            narrative_role=str(payload.get("narrative_role") or "") or None,
            confidence=round(confidence, 4),
        )


def _natural_name(path: Path) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", path.name)
    ]


def collect_images(
    source: Path | str | Sequence[Path],
    *,
    limit: int = 100,
) -> list[Path]:
    if isinstance(source, (str, Path)):
        path = Path(source).expanduser().resolve()
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(
                (item for item in path.iterdir() if item.is_file()),
                key=_natural_name,
            )
        else:
            raise FileNotFoundError(path)
    else:
        candidates = sorted(
            (Path(item).expanduser().resolve() for item in source),
            key=_natural_name,
        )
        missing = [item for item in candidates if not item.is_file()]
        if missing:
            raise FileNotFoundError(missing[0])
    images = [item for item in candidates if item.suffix.lower() in SUPPORTED_IMAGES]
    if not images:
        raise ValueError("No supported images found; provide an image or local image folder")
    if len(images) > limit:
        raise ValueError(f"Image set exceeds the {limit}-asset safety limit")
    return images


def source_digest(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(sha256_path(path).encode("ascii"))
    return digest.hexdigest()


def _orientation(width: int, height: int) -> str:
    if abs(width - height) <= max(width, height) * 0.08:
        return "square"
    return "portrait" if height > width else "landscape"


def _palette(image: Image.Image, colors: int = 5) -> list[PaletteColor]:
    sample = image.convert("RGB")
    sample.thumbnail((256, 256))
    quantized = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    counts = quantized.getcolors(maxcolors=colors) or []
    raw_palette = quantized.getpalette() or []
    total = max(1, sum(count for count, _ in counts))
    result: list[PaletteColor] = []
    for count, color_index in sorted(counts, reverse=True):
        offset = color_index * 3
        rgb = tuple(raw_palette[offset : offset + 3])
        if len(rgb) != 3:
            continue
        result.append(
            PaletteColor(
                hex="#" + "".join(f"{channel:02x}" for channel in rgb),
                share=round(count / total, 4),
            )
        )
    return result


def _edge_density(image: Image.Image) -> float:
    edges = image.convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES)
    pixels = list(
        edges.get_flattened_data() if hasattr(edges, "get_flattened_data") else edges.getdata()
    )
    return round(sum(value >= 40 for value in pixels) / max(1, len(pixels)), 4)


def _visual_center(image: Image.Image) -> tuple[float, float]:
    sample = image.convert("L").resize((64, 64))
    pixels = list(
        sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    )
    mean = sum(pixels) / max(1, len(pixels))
    weights = [abs(value - mean) for value in pixels]
    total = sum(weights)
    if not total:
        return (0.5, 0.5)
    x = sum((index % 64) * weight for index, weight in enumerate(weights)) / total / 63
    y = sum((index // 64) * weight for index, weight in enumerate(weights)) / total / 63
    return (round(x, 4), round(y, 4))


def measure_image(path: Path) -> ImageMeasurement:
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        width, height = image.size
        grayscale = image.convert("L")
        hsv = image.convert("HSV")
        gray_stat = ImageStat.Stat(grayscale.resize((128, 128)))
        saturation = ImageStat.Stat(hsv.resize((128, 128))).mean[1]
        return ImageMeasurement(
            width=width,
            height=height,
            aspect_ratio=round(width / height, 4),
            orientation=_orientation(width, height),
            mode=opened.mode,
            format=(opened.format or path.suffix.removeprefix(".")).lower(),
            size_bytes=path.stat().st_size,
            sha256=sha256_path(path),
            brightness=round(gray_stat.mean[0], 3),
            contrast=round(gray_stat.stddev[0], 3),
            saturation=round(saturation, 3),
            entropy=round(grayscale.entropy(), 4),
            edge_density=_edge_density(image),
            visual_center=_visual_center(image),
            dominant_palette=_palette(image),
        )


def extract_ocr(path: Path) -> OCRResult:
    binary = shutil.which("tesseract")
    if not binary:
        return OCRResult(
            status="unavailable",
            provider="tesseract-missing",
            source_type=EvidenceKind.UNAVAILABLE,
        )
    result = subprocess.run(
        [binary, str(path), "stdout", "tsv"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        return OCRResult(
            status="failed",
            provider="tesseract",
            source_type=EvidenceKind.UNAVAILABLE,
        )
    regions: list[TextRegion] = []
    reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        if not text or confidence < 0:
            continue
        regions.append(
            TextRegion(
                text=text,
                confidence=round(min(1.0, confidence / 100), 4),
                box=BoundingBox(
                    x=max(0, int(row.get("left") or 0)),
                    y=max(0, int(row.get("top") or 0)),
                    width=max(0, int(row.get("width") or 0)),
                    height=max(0, int(row.get("height") or 0)),
                ),
            )
        )
    with Image.open(path) as image:
        area = max(1, image.width * image.height)
        coverage = min(1.0, sum(item.box.width * item.box.height for item in regions) / area)
        thirds = {"top": 0, "middle": 0, "bottom": 0}
        for item in regions:
            center = item.box.y + item.box.height / 2
            if center < image.height / 3:
                band = "top"
            elif center > image.height * 2 / 3:
                band = "bottom"
            else:
                band = "middle"
            thirds[band] += 1
    full_text = " ".join(item.text for item in regions)
    lowered = full_text.casefold()
    cta_evidence = sorted(
        term for term in CTA_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)
    )
    return OCRResult(
        status="succeeded",
        provider="tesseract",
        source_type=EvidenceKind.EXTRACTED,
        text=full_text,
        mean_confidence=(
            round(sum(item.confidence for item in regions) / len(regions), 4) if regions else None
        ),
        regions=regions,
        text_coverage=round(coverage, 4),
        hierarchy=thirds,
        cta_candidate=bool(cta_evidence),
        cta_evidence=cta_evidence,
    )


def _sequence_role(index: int, total: int, ocr: OCRResult) -> str:
    if total == 1:
        return "single_image"
    if index == 1:
        return "hook_candidate"
    if index == total and ocr.cta_candidate:
        return "cta_candidate"
    if index == total:
        return "payoff_or_close_candidate"
    if index == 2:
        return "setup_candidate"
    return "development"


def _contact_sheet(slides: list[ImageSlide], output_dir: Path) -> Path:
    columns = min(4, len(slides))
    cell_width, cell_height = 320, 380
    rows = math.ceil(len(slides) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for position, slide in enumerate(slides):
        with Image.open(output_dir / slide.stored_path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((cell_width - 16, cell_height - 64))
            x = position % columns * cell_width + (cell_width - image.width) // 2
            y = position // columns * cell_height + 8
            sheet.paste(image, (x, y))
        label_y = position // columns * cell_height + cell_height - 48
        draw.text(
            (position % columns * cell_width + 8, label_y),
            f"{slide.index}. {slide.sequence_role}",
            fill="black",
            font=font,
        )
    target = output_dir / "contact-sheet.jpg"
    sheet.save(target, quality=90)
    return target


class ImageReferenceProcessor:
    def __init__(self, observer: ImageObserver | None = None) -> None:
        self.observer = observer

    def process(
        self,
        source: Path | str | Sequence[Path],
        output_root: Path | str,
        *,
        rights: RightsDeclaration,
        title: str | None = None,
        force: bool = False,
    ) -> tuple[ImageReferenceManifest, Path]:
        paths = collect_images(source)
        digest = source_digest(paths)
        reference_id = f"img-{digest[:12]}"
        output_dir = Path(output_root).expanduser().resolve() / reference_id
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "image-reference.json"
        if manifest_path.is_file() and not force:
            previous = ImageReferenceManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            reusable_status = previous.status in {
                ImageRunStatus.SUCCEEDED,
                ImageRunStatus.PARTIAL,
                ImageRunStatus.REUSED,
            }
            stored_assets_valid = all(
                (output_dir / slide.stored_path).is_file()
                and sha256_path(output_dir / slide.stored_path) == slide.measurements.sha256
                for slide in previous.slides
            )
            if (
                previous.source_digest == digest
                and previous.rights_declaration == rights
                and reusable_status
                and stored_assets_valid
            ):
                reused = previous.model_copy(
                    update={
                        "status": ImageRunStatus.REUSED,
                        "title": title or previous.title,
                        "generated_at": datetime.now(UTC),
                    }
                )
                manifest_path.write_text(reused.model_dump_json(indent=2), encoding="utf-8")
                return reused, manifest_path

        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        slides: list[ImageSlide] = []
        failures: list[ImageFailure] = []
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            target = source_dir / f"slide-{index:04d}{path.suffix.lower()}"
            try:
                shutil.copy2(path, target)
                ocr = extract_ocr(target)
                if self.observer:
                    try:
                        observation = self.observer.observe(target, index=index, total=total)
                    except Exception as exc:  # noqa: BLE001 - isolate local model drift
                        observation = ModelObservation(
                            status="failed",
                            provider=self.observer.name,
                            source_type=EvidenceKind.UNAVAILABLE,
                            layout_summary=f"Observation unavailable: {type(exc).__name__}",
                        )
                else:
                    observation = ModelObservation()
                slides.append(
                    ImageSlide(
                        index=index,
                        asset_name=path.name,
                        stored_path=str(target.relative_to(output_dir)),
                        sequence_role=_sequence_role(index, total, ocr),
                        measurements=measure_image(target),
                        ocr=ocr,
                        observation=observation,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - preserve other carousel slides
                failures.append(
                    ImageFailure(
                        index=index,
                        asset_name=path.name,
                        error_type=type(exc).__name__,
                        error=f"Image processing failed: {type(exc).__name__}",
                    )
                )
        contact_sheet = _contact_sheet(slides, output_dir) if slides else None
        carousel_map = [
            CarouselMapEntry(
                index=slide.index,
                role=slide.sequence_role,
                evidence=[
                    "role is a deterministic sequence candidate, not a confirmed narrative fact",
                    f"ocr_status={slide.ocr.status}",
                ],
                confidence=0.75 if slide.ocr.cta_candidate else 0.55,
            )
            for slide in slides
        ]
        limitations = []
        if any(slide.ocr.status != "succeeded" for slide in slides):
            limitations.append("OCR was unavailable or failed for one or more assets.")
        if not self.observer:
            limitations.append(
                "Subjects and semantic intent were not inferred without an explicit "
                "vision provider."
            )
        status = (
            ImageRunStatus.FAILED
            if not slides
            else ImageRunStatus.PARTIAL
            if failures
            else ImageRunStatus.SUCCEEDED
        )
        if title:
            resolved_title = title
        elif isinstance(source, (str, Path)):
            source_path = Path(source)
            resolved_title = source_path.stem if source_path.is_file() else source_path.name
        else:
            resolved_title = "image reference"
        manifest = ImageReferenceManifest(
            reference_id=reference_id,
            title=resolved_title,
            status=status,
            rights_declaration=rights,
            source_digest=digest,
            media_kind="single_image" if total == 1 else "carousel",
            attempted_count=total,
            slide_count=len(slides),
            slides=slides,
            failures=failures,
            carousel_map=carousel_map,
            contact_sheet=(str(contact_sheet.relative_to(output_dir)) if contact_sheet else None),
            limitations=limitations,
        )
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        (output_dir / "analysis-summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "p75.image_summary.v1",
                    "reference_id": reference_id,
                    "media_kind": manifest.media_kind,
                    "attempted_count": total,
                    "slide_count": len(slides),
                    "orientations": [slide.measurements.orientation for slide in slides],
                    "sequence_roles": [slide.sequence_role for slide in slides],
                    "human_review_required": True,
                    "source_reuse_allowed": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest, manifest_path
