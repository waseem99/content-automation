from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from refintel.acquisition import (
    AcquiredAsset,
    AcquisitionManifest,
    AcquisitionService,
    AcquisitionStatus,
    AssetRole,
    safe_source_url,
    sanitize_diagnostic,
    sha256_path,
)
from refintel.adapters import AcquisitionRoute, normalize_reference
from refintel.ingest import IngestionService
from refintel.models import Platform, ProjectStatus, RightsDeclaration
from refintel.storage import WorkspaceStore


class FakeDownloader:
    def __init__(
        self,
        options: dict[str, object],
        *,
        info: dict[str, Any] | None = None,
        error: Exception | None = None,
        create_assets: bool = True,
    ) -> None:
        self.options = options
        self.info = info or {}
        self.error = error
        self.create_assets = create_assets

    def __enter__(self) -> FakeDownloader:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def extract_info(self, _url: str, *, download: bool) -> dict[str, Any]:
        if self.error:
            raise self.error
        if download and self.create_assets:
            template = str(self.options["outtmpl"])
            video = Path(template.replace("%(ext)s", "mp4"))
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b"authorized-fixture-video")
            video.with_suffix(".webp").write_bytes(b"fixture-thumbnail")
            video.with_suffix(".info.json").write_text("{}", encoding="utf-8")
        return self.info


def test_acquisition_writes_resumable_sanitized_asset_manifest(tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    def factory(options: dict[str, object]) -> FakeDownloader:
        captured.append(options)
        return FakeDownloader(
            options,
            info={
                "id": "abc123",
                "title": "Authorized reference",
                "uploader": "Creator",
                "duration": 31.5,
                "webpage_url": "https://private.invalid/?token=placeholder",
            },
        )

    outcome = AcquisitionService(downloader_factory=factory).acquire(
        "https://www.youtube.com/watch?v=abc123&utm_source=test&token=placeholder",
        tmp_path,
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )

    assert outcome.manifest.status == AcquisitionStatus.SUCCEEDED
    assert outcome.primary_path.name == "original.mp4"
    assert outcome.manifest.reference.canonical_url == (
        "https://youtube.com/watch?v=abc123"
    )
    assert outcome.manifest.metadata == {
        "id": "abc123",
        "title": "Authorized reference",
        "uploader": "Creator",
        "duration": 31.5,
    }
    assert outcome.manifest.human_review_required is True
    assert outcome.manifest.source_media_must_not_enter_generated_content is True
    assert any(asset.role == AssetRole.PRIMARY_VIDEO for asset in outcome.manifest.assets)
    assert all(len(asset.sha256) == 64 for asset in outcome.manifest.assets)
    manifest_text = outcome.manifest_path.read_text(encoding="utf-8")
    assert "placeholder" not in manifest_text
    assert "private.invalid" not in manifest_text

    options = captured[0]
    assert options["continuedl"] is True
    assert options["overwrites"] is False
    assert options["concurrent_fragment_downloads"] == 1
    assert options["sleep_interval_requests"] == 1.0
    assert str(options["download_archive"]).endswith(".download-archive")


def test_successful_acquisition_is_reused_only_when_primary_hash_matches(
    tmp_path: Path,
) -> None:
    calls = 0

    def factory(options: dict[str, object]) -> FakeDownloader:
        nonlocal calls
        calls += 1
        return FakeDownloader(options, info={"id": "abc"})

    service = AcquisitionService(downloader_factory=factory)
    first = service.acquire(
        "https://youtu.be/abc",
        tmp_path,
        rights=RightsDeclaration.PERMITTED,
    )
    second = service.acquire(
        "https://youtu.be/abc",
        tmp_path,
        rights=RightsDeclaration.PERMITTED,
    )
    assert first.manifest.status == AcquisitionStatus.SUCCEEDED
    assert second.manifest.status == AcquisitionStatus.REUSED
    assert calls == 1

    second.primary_path.write_bytes(b"tampered")
    third = service.acquire(
        "https://youtu.be/abc",
        tmp_path,
        rights=RightsDeclaration.PERMITTED,
    )
    assert third.manifest.status == AcquisitionStatus.SUCCEEDED
    assert calls == 2


def test_failed_item_persists_redacted_diagnostics_and_local_fallback(
    tmp_path: Path,
) -> None:
    cookie_file = tmp_path / "private" / "cookies.txt"
    cookie_file.parent.mkdir()
    cookie_file.write_text("secret-cookie", encoding="utf-8")

    def factory(options: dict[str, object]) -> FakeDownloader:
        return FakeDownloader(
            options,
            error=RuntimeError(f"token=abc failed with cookie={cookie_file}"),
        )

    with pytest.raises(RuntimeError):
        AcquisitionService(downloader_factory=factory).acquire(
            "https://www.instagram.com/reel/example/",
            tmp_path,
            rights=RightsDeclaration.PERMITTED,
            cookie_file=cookie_file,
        )
    payload = json.loads(
        (tmp_path / "source" / "acquisition-manifest.json").read_text(encoding="utf-8")
    )
    rendered = json.dumps(payload)
    assert payload["status"] == "failed"
    assert "<redacted>" in rendered
    assert "abc" not in rendered
    assert str(cookie_file) not in rendered
    assert "ingest-file" in payload["fallback_action"]
    assert payload["authentication"] == "authorized_local_browser"


def test_snapchat_failure_reports_experimental_local_export_fallback(
    tmp_path: Path,
) -> None:
    def factory(options: dict[str, object]) -> FakeDownloader:
        return FakeDownloader(options, error=RuntimeError("unsupported extractor"))

    with pytest.raises(RuntimeError):
        AcquisitionService(downloader_factory=factory).acquire(
            "https://www.snapchat.com/spotlight/public-id",
            tmp_path,
            rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
        )
    payload = json.loads(
        (tmp_path / "source" / "acquisition-manifest.json").read_text(encoding="utf-8")
    )
    assert payload["reference"]["platform"] == "snapchat"
    assert "experimental" in payload["fallback_action"].lower()
    assert "ingest-file" in payload["fallback_action"]


def test_youtube_collection_discovery_normalizes_flat_entries() -> None:
    def factory(options: dict[str, object]) -> FakeDownloader:
        assert options["skip_download"] is True
        assert options["extract_flat"] == "in_playlist"
        return FakeDownloader(
            options,
            create_assets=False,
            info={
                "entries": [
                    {
                        "id": "first",
                        "url": "first",
                        "title": "First video",
                        "duration": 21,
                    },
                    {
                        "id": "second",
                        "webpage_url": "https://youtube.com/shorts/second?si=tracking",
                        "title": "Second video",
                    },
                ]
            },
        )

    manifest = AcquisitionService(downloader_factory=factory).discover(
        "https://www.youtube.com/@creator",
        limit=10,
    )
    assert manifest.status == AcquisitionStatus.SUCCEEDED
    assert manifest.platform == Platform.YOUTUBE
    assert [entry.url for entry in manifest.entries] == [
        "https://youtube.com/watch?v=first",
        "https://youtube.com/shorts/second",
    ]


def test_facebook_and_snapchat_profiles_route_to_specialized_fallbacks() -> None:
    service = AcquisitionService(downloader_factory=lambda options: FakeDownloader(options))
    with pytest.raises(ValueError, match="facebook-page"):
        service.discover("https://www.facebook.com/RawrNationTV")
    with pytest.raises(ValueError, match="unsupported"):
        service.discover("https://www.snapchat.com/add/creator")
    with pytest.raises(ValueError, match="unavailable"):
        service.discover("https://example.com/channel")


def test_secret_helpers_remove_sensitive_values_and_private_paths(tmp_path: Path) -> None:
    assert safe_source_url(
        "https://example.com/video?id=1&token=secret&signature=hidden#fragment"
    ) == "https://example.com/video?id=1"
    private = tmp_path / "cookie.txt"
    result = sanitize_diagnostic(
        f"Authorization=Bearer123 failed at {private}", private_paths=[private]
    )
    assert "Bearer123" not in result
    assert str(private) not in result
    assert "<redacted>" in result


def test_ingestion_service_persists_safe_provenance_and_acquisition_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAcquisitionService:
        def acquire(self, _url: str, workspace: Path, **_kwargs: object) -> SimpleNamespace:
            primary = workspace / "source" / "original.mp4"
            primary.write_bytes(b"authorized-reference")
            (workspace / "source" / "acquisition-manifest.json").write_text(
                "{}", encoding="utf-8"
            )
            return SimpleNamespace(
                primary_path=primary,
                manifest=SimpleNamespace(
                    metadata={"title": "Safe title", "uploader": "Creator"},
                    status=AcquisitionStatus.SUCCEEDED,
                    assets=[object()],
                ),
            )

    monkeypatch.setattr("refintel.ingest.AcquisitionService", FakeAcquisitionService)
    store = WorkspaceStore(tmp_path / "library")
    project = IngestionService(store).ingest_url(
        "https://youtube.com/watch?v=abc&token=placeholder&utm_source=test",
        rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
    )
    assert project.status == ProjectStatus.INGESTED
    assert str(project.source.original_url) == "https://youtube.com/watch?v=abc"
    assert project.source.title == "Safe title"
    assert len(project.source.source_sha256 or "") == 64
    rendered = store.project_path(project.reference_id).read_text(encoding="utf-8")
    assert "placeholder" not in rendered
    with store.connection() as connection:
        details = connection.execute(
            "SELECT details_json FROM processing_events WHERE reference_id = ?",
            (project.reference_id,),
        ).fetchone()["details_json"]
    assert json.loads(details)["manifest"] == "source/acquisition-manifest.json"


def test_ingestion_retries_failed_cached_url_instead_of_claiming_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class RecoveringAcquisitionService:
        def acquire(self, _url: str, workspace: Path, **_kwargs: object) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("simulated missing ffmpeg")
            primary = workspace / "source" / "original.mp4"
            primary.write_bytes(b"verified-video")
            asset = SimpleNamespace(
                relative_path="source/original.mp4", sha256=sha256_path(primary)
            )
            manifest = AcquisitionManifest(
                acquisition_id="acq-recovery",
                reference=normalize_reference("https://youtube.com/watch?v=recovery"),
                rights_declaration=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH,
                status=AcquisitionStatus.SUCCEEDED,
                route=AcquisitionRoute.EXTRACTOR,
                primary_asset="source/original.mp4",
                assets=[
                    AcquiredAsset(
                        relative_path=asset.relative_path,
                        role=AssetRole.PRIMARY_VIDEO,
                        media_type="video/mp4",
                        size_bytes=primary.stat().st_size,
                        sha256=asset.sha256,
                    )
                ],
            )
            (workspace / "source" / "acquisition-manifest.json").write_text(
                manifest.model_dump_json(), encoding="utf-8"
            )
            return SimpleNamespace(primary_path=primary, manifest=manifest)

    monkeypatch.setattr(
        "refintel.ingest.AcquisitionService", RecoveringAcquisitionService
    )
    service = IngestionService(WorkspaceStore(tmp_path / "library"))
    url = "https://youtube.com/watch?v=recovery"
    with pytest.raises(RuntimeError, match="missing ffmpeg"):
        service.ingest_url(url, rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH)

    recovered = service.ingest_url(
        url, rights=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH
    )

    assert calls == 2
    assert recovered.status == ProjectStatus.INGESTED
