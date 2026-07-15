from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from .adapters import (
    AcquisitionRoute,
    NormalizedReference,
    ReferenceInputType,
    SupportLevel,
    normalize_reference,
)
from .models import Platform, RightsDeclaration


class AcquisitionStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REUSED = "reused"


class AssetRole(StrEnum):
    PRIMARY_VIDEO = "primary_video"
    PRIMARY_IMAGE = "primary_image"
    THUMBNAIL = "thumbnail"
    SUBTITLE = "subtitle"
    METADATA = "metadata"
    AUXILIARY = "auxiliary"


class AcquisitionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retries: int = Field(default=3, ge=0, le=10)
    fragment_retries: int = Field(default=3, ge=0, le=10)
    extractor_retries: int = Field(default=2, ge=0, le=10)
    file_access_retries: int = Field(default=3, ge=0, le=10)
    socket_timeout_seconds: int = Field(default=30, ge=5, le=120)
    request_sleep_seconds: float = Field(default=1.0, ge=0, le=30)
    max_sleep_seconds: float = Field(default=3.0, ge=0, le=60)
    rate_limit_bytes_per_second: int | None = Field(default=None, ge=1024)
    continue_partial_downloads: bool = True


class AcquiredAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str
    role: AssetRole
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str


class AcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.acquisition.v1"
    acquisition_id: str
    reference: NormalizedReference
    rights_declaration: RightsDeclaration
    status: AcquisitionStatus
    route: AcquisitionRoute
    extractor: str = "yt-dlp"
    attempt_count: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    primary_asset: str | None = None
    assets: list[AcquiredAsset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    fallback_action: str = "Use ingest-file with an authorized local export."
    authentication: str = "public"
    resumable: bool = True
    human_review_required: bool = True
    source_media_must_not_enter_generated_content: bool = True


class DiscoveryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    media_id: str | None = None
    title: str | None = None
    uploader: str | None = None
    duration_seconds: float | None = None


class DiscoveryManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.discovery.v1"
    source: NormalizedReference
    platform: Platform
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: AcquisitionStatus
    entries: list[DiscoveryEntry] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    fallback_action: str = "Provide direct public media URLs or authorized local files."
    partial_results_possible: bool = True
    human_review_required: bool = True


class AcquisitionOutcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: AcquisitionManifest
    manifest_path: Path
    primary_path: Path


class Downloader(Protocol):
    def __enter__(self) -> Downloader: ...

    def __exit__(self, *args: object) -> None: ...

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any]: ...


DownloaderFactory = Callable[[dict[str, object]], Downloader]

VIDEO_EXTENSIONS = {".m4v", ".mkv", ".mov", ".mp4", ".webm"}
IMAGE_EXTENSIONS = {".avif", ".jpeg", ".jpg", ".png", ".webp"}
SUBTITLE_EXTENSIONS = {".ass", ".srt", ".vtt"}
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
}
SECRET_PATTERN = re.compile(
    r"(?i)(authorization|cookie|password|secret|token)\s*[:=]\s*[^\s,;]+"
)


def sha256_path(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def safe_source_url(url: str) -> str:
    parsed = urlsplit(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in SENSITIVE_QUERY_KEYS
        ]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def sanitize_diagnostic(
    value: object,
    *,
    private_paths: Iterable[Path | str] = (),
) -> str:
    sanitized = str(value).replace("\n", " ")[:2000]
    for path in private_paths:
        rendered = str(path)
        if rendered:
            sanitized = sanitized.replace(rendered, "<private-local-path>")
    sanitized = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", sanitized)
    return sanitized


def _asset_role(path: Path, primary: Path | None) -> AssetRole:
    if primary and path == primary:
        return (
            AssetRole.PRIMARY_VIDEO
            if path.suffix.lower() in VIDEO_EXTENSIONS
            else AssetRole.PRIMARY_IMAGE
        )
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return AssetRole.THUMBNAIL
    if path.suffix.lower() in SUBTITLE_EXTENSIONS:
        return AssetRole.SUBTITLE
    if path.suffix.lower() == ".json":
        return AssetRole.METADATA
    return AssetRole.AUXILIARY


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return f"video/{suffix.removeprefix('.')}"
    if suffix in IMAGE_EXTENSIONS:
        subtype = "jpeg" if suffix in {".jpg", ".jpeg"} else suffix.removeprefix(".")
        return f"image/{subtype}"
    if suffix in SUBTITLE_EXTENSIONS:
        return "text/vtt" if suffix == ".vtt" else "text/plain"
    if suffix == ".json":
        return "application/json"
    return "application/octet-stream"


def _primary_asset(source_dir: Path) -> Path | None:
    candidates = [
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
    ]
    if not candidates:
        return None
    videos = [path for path in candidates if path.suffix.lower() in VIDEO_EXTENSIONS]
    return max(videos or candidates, key=lambda path: path.stat().st_size)


def _inventory(source_dir: Path, manifest_path: Path, primary: Path) -> list[AcquiredAsset]:
    assets: list[AcquiredAsset] = []
    for path in sorted(source_dir.iterdir()):
        if (
            not path.is_file()
            or path in {manifest_path, source_dir / ".download-archive"}
            or path.name.endswith((".invalid", ".part"))
        ):
            continue
        assets.append(
            AcquiredAsset(
                relative_path=str(path.relative_to(source_dir.parent)),
                role=_asset_role(path, primary),
                media_type=_media_type(path),
                size_bytes=path.stat().st_size,
                sha256=sha256_path(path),
            )
        )
    return assets


def _allowlisted_metadata(info: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "id",
        "title",
        "uploader",
        "channel",
        "duration",
        "timestamp",
        "upload_date",
        "extractor",
        "extractor_key",
        "view_count",
        "like_count",
        "comment_count",
        "width",
        "height",
        "fps",
        "ext",
    )
    return {key: info[key] for key in allowed if info.get(key) is not None}


class AcquisitionService:
    def __init__(
        self,
        *,
        policy: AcquisitionPolicy | None = None,
        downloader_factory: DownloaderFactory | None = None,
    ) -> None:
        self.policy = policy or AcquisitionPolicy()
        self.downloader_factory = downloader_factory

    def acquire(
        self,
        url: str,
        workspace: Path,
        *,
        rights: RightsDeclaration,
        cookies_from_browser: str | None = None,
        cookie_file: Path | None = None,
    ) -> AcquisitionOutcome:
        reference = normalize_reference(url)
        if reference.input_type != ReferenceInputType.DIRECT_MEDIA:
            raise ValueError(
                "A direct media URL is required. Discover profile/page candidates first."
            )
        if reference.support == SupportLevel.UNSUPPORTED:
            raise ValueError("This URL route is unsupported; use an authorized local export.")

        source_dir = workspace / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = source_dir / "acquisition-manifest.json"
        persisted_reference = reference.model_copy(
            update={"original_url": safe_source_url(reference.canonical_url)}
        )
        previous = self._load_manifest(manifest_path)
        if previous and previous.status in {
            AcquisitionStatus.SUCCEEDED,
            AcquisitionStatus.REUSED,
        }:
            primary = source_dir.parent / str(previous.primary_asset)
            primary_record = next(
                (
                    asset
                    for asset in previous.assets
                    if asset.relative_path == previous.primary_asset
                ),
                None,
            )
            if (
                primary.is_file()
                and primary_record is not None
                and sha256_path(primary) == primary_record.sha256
            ):
                previous.status = AcquisitionStatus.REUSED
                previous.completed_at = datetime.now(UTC)
                self._write_manifest(previous, manifest_path)
                return AcquisitionOutcome(
                    manifest=previous,
                    manifest_path=manifest_path,
                    primary_path=primary,
                )
            self._quarantine_invalid_resume(source_dir, primary)

        manifest = AcquisitionManifest(
            acquisition_id=f"acq-{hashlib.sha256(reference.canonical_url.encode()).hexdigest()[:12]}",
            reference=persisted_reference,
            rights_declaration=rights,
            status=AcquisitionStatus.RUNNING,
            route=reference.route,
            attempt_count=(previous.attempt_count if previous else 0) + 1,
            started_at=datetime.now(UTC),
            authentication=(
                "authorized_local_browser"
                if cookies_from_browser or cookie_file
                else "public"
            ),
        )
        self._write_manifest(manifest, manifest_path)
        private_paths = [path for path in (cookie_file,) if path]
        try:
            options = self._downloader_options(
                source_dir,
                cookies_from_browser=cookies_from_browser,
                cookie_file=cookie_file,
            )
            with self._downloader(options) as downloader:
                info = downloader.extract_info(url, download=True)
            if not isinstance(info, dict):
                info = {}
            primary = _primary_asset(source_dir)
            if not primary:
                raise RuntimeError("The extractor produced no supported video or image asset")
            manifest.assets = _inventory(source_dir, manifest_path, primary)
            manifest.primary_asset = str(primary.relative_to(workspace))
            manifest.metadata = _allowlisted_metadata(info)
            manifest.status = AcquisitionStatus.SUCCEEDED
            manifest.completed_at = datetime.now(UTC)
            self._write_manifest(manifest, manifest_path)
            return AcquisitionOutcome(
                manifest=manifest,
                manifest_path=manifest_path,
                primary_path=primary,
            )
        except Exception as exc:
            manifest.status = AcquisitionStatus.FAILED
            manifest.completed_at = datetime.now(UTC)
            manifest.diagnostics.append(
                sanitize_diagnostic(exc, private_paths=private_paths)
            )
            if reference.platform == Platform.SNAPCHAT:
                manifest.fallback_action = (
                    "Snapchat extraction is experimental. Export the authorized public "
                    "Spotlight/Story locally and use ingest-file."
                )
            self._write_manifest(manifest, manifest_path)
            raise

    def discover(
        self,
        url: str,
        *,
        limit: int = 20,
        cookies_from_browser: str | None = None,
        cookie_file: Path | None = None,
    ) -> DiscoveryManifest:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        reference = normalize_reference(url)
        persisted_reference = reference.model_copy(
            update={"original_url": safe_source_url(reference.canonical_url)}
        )
        if reference.platform == Platform.FACEBOOK:
            raise ValueError("Use facebook-page with the dedicated local Playwright profile.")
        if reference.platform == Platform.SNAPCHAT:
            raise ValueError(
                "Snapchat profile discovery is unsupported; provide a public direct link "
                "or authorized local export."
            )
        if reference.platform not in {
            Platform.YOUTUBE,
            Platform.INSTAGRAM,
            Platform.TIKTOK,
            Platform.X,
        }:
            raise ValueError(
                "Discovery is unavailable for this platform; provide direct public media "
                "URLs or authorized local files."
            )
        if reference.input_type == ReferenceInputType.DIRECT_MEDIA:
            raise ValueError(
                "Use ingest-url for direct media; discovery expects a page/collection."
            )

        private_paths = [path for path in (cookie_file,) if path]
        try:
            options = self._discovery_options(
                limit,
                cookies_from_browser=cookies_from_browser,
                cookie_file=cookie_file,
            )
            with self._downloader(options) as downloader:
                info = downloader.extract_info(url, download=False)
            if not isinstance(info, dict):
                raise RuntimeError("The extractor returned no discovery metadata")
            entries = self._discovery_entries(info, reference.platform, limit)
            return DiscoveryManifest(
                source=persisted_reference,
                platform=reference.platform,
                status=AcquisitionStatus.SUCCEEDED,
                entries=entries,
            )
        except Exception as exc:
            return DiscoveryManifest(
                source=persisted_reference,
                platform=reference.platform,
                status=AcquisitionStatus.FAILED,
                diagnostics=[sanitize_diagnostic(exc, private_paths=private_paths)],
            )

    def _downloader(self, options: dict[str, object]) -> Downloader:
        if self.downloader_factory:
            return self.downloader_factory(options)
        try:
            import yt_dlp  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install the media extra to enable URL acquisition") from exc
        return yt_dlp.YoutubeDL(options)

    def _downloader_options(
        self,
        source_dir: Path,
        *,
        cookies_from_browser: str | None,
        cookie_file: Path | None,
    ) -> dict[str, object]:
        options: dict[str, object] = {
            "outtmpl": str(source_dir / "original.%(ext)s"),
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "writesubtitles": True,
            "writeautomaticsub": True,
            "writethumbnail": True,
            "writeinfojson": True,
            "noplaylist": True,
            "continuedl": self.policy.continue_partial_downloads,
            "overwrites": False,
            "download_archive": str(source_dir / ".download-archive"),
            "retries": self.policy.retries,
            "fragment_retries": self.policy.fragment_retries,
            "extractor_retries": self.policy.extractor_retries,
            "file_access_retries": self.policy.file_access_retries,
            "socket_timeout": self.policy.socket_timeout_seconds,
            "sleep_interval_requests": self.policy.request_sleep_seconds,
            "sleep_interval": self.policy.request_sleep_seconds,
            "max_sleep_interval": self.policy.max_sleep_seconds,
            "concurrent_fragment_downloads": 1,
            "quiet": True,
            "no_warnings": True,
        }
        if self.policy.rate_limit_bytes_per_second:
            options["ratelimit"] = self.policy.rate_limit_bytes_per_second
        self._attach_local_auth(
            options,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
        )
        return options

    def _discovery_options(
        self,
        limit: int,
        *,
        cookies_from_browser: str | None,
        cookie_file: Path | None,
    ) -> dict[str, object]:
        options: dict[str, object] = {
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playlistend": limit,
            "lazy_playlist": True,
            "ignoreerrors": True,
            "socket_timeout": self.policy.socket_timeout_seconds,
            "extractor_retries": self.policy.extractor_retries,
            "sleep_interval_requests": self.policy.request_sleep_seconds,
            "quiet": True,
            "no_warnings": True,
        }
        self._attach_local_auth(
            options,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
        )
        return options

    @staticmethod
    def _attach_local_auth(
        options: dict[str, object],
        *,
        cookies_from_browser: str | None,
        cookie_file: Path | None,
    ) -> None:
        if cookies_from_browser and cookie_file:
            raise ValueError("Use either cookies_from_browser or cookie_file, not both")
        if cookies_from_browser:
            options["cookiesfrombrowser"] = (cookies_from_browser,)
        if cookie_file:
            options["cookiefile"] = str(cookie_file)

    @staticmethod
    def _discovery_entries(
        info: dict[str, Any],
        platform: Platform,
        limit: int,
    ) -> list[DiscoveryEntry]:
        raw_entries = info.get("entries") or []
        entries: list[DiscoveryEntry] = []
        seen: set[str] = set()
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            media_id = str(raw.get("id")) if raw.get("id") is not None else None
            candidate = raw.get("webpage_url") or raw.get("url")
            if platform == Platform.YOUTUBE and candidate and not str(candidate).startswith(
                ("http://", "https://")
            ):
                candidate = f"https://www.youtube.com/watch?v={candidate}"
            if not candidate or not str(candidate).startswith(("http://", "https://")):
                continue
            try:
                safe_url = normalize_reference(str(candidate)).canonical_url
            except ValueError:
                safe_url = safe_source_url(str(candidate))
            if safe_url in seen:
                continue
            seen.add(safe_url)
            entries.append(
                DiscoveryEntry(
                    url=safe_url,
                    media_id=media_id,
                    title=str(raw.get("title")) if raw.get("title") else None,
                    uploader=str(raw.get("uploader")) if raw.get("uploader") else None,
                    duration_seconds=(
                        float(raw["duration"]) if raw.get("duration") is not None else None
                    ),
                )
            )
            if len(entries) >= limit:
                break
        return entries

    @staticmethod
    def _load_manifest(path: Path) -> AcquisitionManifest | None:
        if not path.is_file():
            return None
        try:
            return AcquisitionManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return None

    @staticmethod
    def _quarantine_invalid_resume(source_dir: Path, primary: Path) -> None:
        suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        for path in (primary, source_dir / ".download-archive"):
            if path.is_file():
                quarantine = path.with_name(f"{path.name}.{suffix}.invalid")
                path.replace(quarantine)

    @staticmethod
    def _write_manifest(manifest: AcquisitionManifest, path: Path) -> None:
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
