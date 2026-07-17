from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from refintel.images import (
    EvidenceKind,
    ImageReferenceProcessor,
    ImageRunStatus,
    ModelObservation,
    OCRResult,
    collect_images,
)
from refintel.models import RightsDeclaration
from refintel.pipeline import ReferencePipeline
from refintel.settings import RefIntelSettings


def make_image(path: Path, color: str, text: str = "") -> None:
    image = Image.new("RGB", (720, 1080), color)
    if text:
        ImageDraw.Draw(image).text((60, 90), text, fill="white")
    image.save(path)


def no_ocr(_path: Path) -> OCRResult:
    return OCRResult(
        status="unavailable",
        provider="test-no-ocr",
        source_type=EvidenceKind.UNAVAILABLE,
    )


def test_image_carousel_is_measured_ordered_and_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "carousel"
    source.mkdir()
    make_image(source / "slide-10.png", "#003366")
    make_image(source / "slide-2.png", "#336699")
    make_image(source / "slide-1.png", "#cc5500")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)

    processor = ImageReferenceProcessor()
    first, path = processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
        title="Authorized carousel",
    )
    second, _ = processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )

    assert first.status == ImageRunStatus.SUCCEEDED
    assert second.status == ImageRunStatus.REUSED
    assert [slide.asset_name for slide in first.slides] == [
        "slide-1.png",
        "slide-2.png",
        "slide-10.png",
    ]
    assert [slide.sequence_role for slide in first.slides] == [
        "hook_candidate",
        "setup_candidate",
        "payoff_or_close_candidate",
    ]
    assert first.slides[0].measurements.orientation == "portrait"
    assert first.slides[0].measurements.dominant_palette
    assert len(first.slides[0].measurements.sha256) == 64
    assert (path.parent / str(first.contact_sheet)).is_file()
    assert first.human_review_required is True
    assert first.source_text_must_not_be_reused_verbatim is True
    assert first.source_media_must_not_enter_generated_content is True
    assert first.automatic_publication is False


def test_resume_rebuilds_when_stored_asset_hash_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "single.png"
    make_image(source, "#116633")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)
    processor = ImageReferenceProcessor()
    first, path = processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.OWNED,
    )
    stored = path.parent / first.slides[0].stored_path
    stored.write_bytes(b"tampered")

    rebuilt, _ = processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.OWNED,
    )
    assert rebuilt.status == ImageRunStatus.SUCCEEDED
    assert stored.read_bytes() != b"tampered"


def test_resume_never_reuses_a_different_rights_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "single.png"
    make_image(source, "#663311")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)
    processor = ImageReferenceProcessor()
    processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )
    rebuilt, _ = processor.process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PERMITTED,
    )
    assert rebuilt.status == ImageRunStatus.SUCCEEDED
    assert rebuilt.rights_declaration == RightsDeclaration.PERMITTED


def test_ocr_cta_evidence_can_mark_only_the_closing_slide_as_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "carousel"
    source.mkdir()
    make_image(source / "01.png", "#111111")
    make_image(source / "02.png", "#eeeeee")
    calls = 0

    def fixture_ocr(_path: Path) -> OCRResult:
        nonlocal calls
        calls += 1
        return OCRResult(
            status="succeeded",
            provider="fixture-ocr",
            source_type=EvidenceKind.EXTRACTED,
            text="Shop now" if calls == 2 else "Opening claim",
            cta_candidate=calls == 2,
            cta_evidence=["shop now"] if calls == 2 else [],
        )

    monkeypatch.setattr("refintel.images.extract_ocr", fixture_ocr)
    manifest, _ = ImageReferenceProcessor().process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PERMITTED,
    )
    assert manifest.slides[-1].sequence_role == "cta_candidate"
    assert manifest.carousel_map[-1].confidence == 0.75
    assert "candidate" in manifest.carousel_map[-1].evidence[0]


def test_optional_observer_is_labeled_as_model_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "single.png"
    make_image(source, "#224466")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)

    class FixtureObserver:
        name = "fixture-observer"

        def observe(self, _path: Path, *, index: int, total: int) -> ModelObservation:
            assert (index, total) == (1, 1)
            return ModelObservation(
                status="succeeded",
                provider=self.name,
                source_type=EvidenceKind.MODEL_OBSERVATION,
                subjects=["generic product package"],
                layout_summary="Centered subject with upper text zone.",
                confidence=0.8,
            )

    manifest, _ = ImageReferenceProcessor(observer=FixtureObserver()).process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.OWNED,
    )
    assert manifest.media_kind == "single_image"
    assert manifest.slides[0].observation.subjects == ["generic product package"]
    assert manifest.slides[0].observation.source_type == EvidenceKind.MODEL_OBSERVATION


def test_corrupt_carousel_asset_is_isolated_and_manifest_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "carousel"
    source.mkdir()
    make_image(source / "01.png", "#445566")
    (source / "02.png").write_bytes(b"not-an-image")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)

    manifest, path = ImageReferenceProcessor().process(
        source,
        tmp_path / "runs",
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert manifest.status == ImageRunStatus.PARTIAL
    assert manifest.attempted_count == 2
    assert manifest.slide_count == 1
    assert manifest.failures[0].asset_name == "02.png"
    assert str(source) not in json.dumps(payload)
    assert "readable authorized local image" in manifest.failures[0].fallback_action


def test_image_folder_requires_supported_media(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not media", encoding="utf-8")
    with pytest.raises(ValueError, match="No supported images"):
        collect_images(tmp_path)


def test_env_settings_accept_paths_not_cookie_contents(tmp_path: Path) -> None:
    cookie = tmp_path / "facebook-cookies.txt"
    cookie.write_text("fixture", encoding="utf-8")
    settings = RefIntelSettings.from_env(
        {
            "REFINTEL_WORKSPACE": str(tmp_path / "workspace"),
            "REFINTEL_FACEBOOK_PROFILE": str(tmp_path / "profile"),
            "REFINTEL_FACEBOOK_COOKIE_FILE": str(cookie),
            "REFINTEL_USE_OLLAMA": "1",
        }
    )
    settings.validate_local_auth()
    assert settings.facebook_cookie_file == cookie.resolve()
    assert settings.use_ollama is True


def test_env_settings_reject_conflicting_auth_routes(tmp_path: Path) -> None:
    cookie = tmp_path / "facebook-cookies.txt"
    cookie.write_text("fixture", encoding="utf-8")
    settings = RefIntelSettings.from_env(
        {
            "REFINTEL_FACEBOOK_COOKIE_FILE": str(cookie),
            "REFINTEL_COOKIES_FROM_BROWSER": "chrome",
        }
    )
    with pytest.raises(ValueError, match="either"):
        settings.validate_local_auth()


def test_canonical_pipeline_dispatches_local_image_without_video_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "reference.png"
    make_image(source, "#335577")
    monkeypatch.setattr("refintel.images.extract_ocr", no_ocr)
    engine = ReferencePipeline(tmp_path / "workspace")
    project = engine.ingest_file(
        source,
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )

    completed = engine.process(project.reference_id, use_local_vision=False)
    manifests = list(
        (Path(completed.workspace_path) / "image-analysis").glob("*/image-reference.json")
    )
    assert completed.status.value == "complete"
    assert len(manifests) == 1
    payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert payload["media_kind"] == "single_image"
    assert payload["source_media_must_not_enter_generated_content"] is True
