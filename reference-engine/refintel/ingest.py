from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from .acquisition import (
    AcquisitionManifest,
    AcquisitionService,
    AcquisitionStatus,
    sanitize_diagnostic,
)
from .adapters import (
    ReferenceInputType,
    canonicalize_url,
    normalize_reference,
)
from .models import (
    Platform,
    ProjectStatus,
    ReferenceProject,
    RightsDeclaration,
    SourceAccess,
    SourceDescriptor,
)
from .storage import WorkspaceStore

LOCAL_COOKIE_BROWSERS = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_direct_video_url(url: str) -> Platform:
    """Require a direct video/post URL instead of a platform profile or home page."""
    reference = normalize_reference(url)
    if reference.input_type == ReferenceInputType.DIRECT_MEDIA:
        return reference.platform
    supported = "Facebook, Instagram, YouTube, TikTok, X, or Snapchat"
    if reference.platform == Platform.UNKNOWN:
        raise ValueError(
            f"Unsupported platform URL. Use a direct {supported} video URL or ingest-file."
        )
    if reference.requires_resolution:
        raise ValueError(
            f"{reference.platform.value} share links must be resolved to a direct media URL "
            "before ingestion, or use ingest-file with an authorized local copy."
        )
    raise ValueError(
        f"{reference.platform.value} profile/page URLs are not direct video inputs. "
        "Use a direct reel/video/post URL or ingest-file with an authorized local copy."
    )


def validate_local_cookie_browser(browser: str | None) -> str | None:
    if browser is None:
        return None
    normalized = browser.strip().lower()
    if normalized not in LOCAL_COOKIE_BROWSERS:
        raise ValueError(
            "cookies_from_browser must name a supported local browser: "
            + ", ".join(sorted(LOCAL_COOKIE_BROWSERS))
        )
    return normalized


def canonical_url_key(url: str) -> str:
    return f"url:{canonicalize_url(url)}"


def reference_id_from_key(canonical_key: str) -> str:
    return f"ref-{hashlib.sha256(canonical_key.encode('utf-8')).hexdigest()[:12]}"


def has_valid_cached_acquisition(project: ReferenceProject) -> bool:
    """Only reuse a URL acquisition whose manifest and primary bytes both verify."""
    workspace = Path(project.workspace_path)
    manifest_path = workspace / "source" / "acquisition-manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = AcquisitionManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except ValueError:
        return False
    if manifest.status not in {AcquisitionStatus.SUCCEEDED, AcquisitionStatus.REUSED}:
        return False
    if not manifest.primary_asset:
        return False
    primary = workspace / manifest.primary_asset
    record = next(
        (asset for asset in manifest.assets if asset.relative_path == manifest.primary_asset),
        None,
    )
    return bool(
        primary.is_file()
        and primary.stat().st_size > 0
        and record is not None
        and record.sha256 == sha256_file(primary)
    )


class IngestionService:
    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store

    def ingest_file(
        self,
        source_path: Path | str,
        *,
        rights: RightsDeclaration,
        title: str | None = None,
        operator_note: str | None = None,
        force_new: bool = False,
    ) -> ReferenceProject:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        source_hash = sha256_file(source)
        canonical_key = f"sha256:{source_hash}"
        existing_id = self.store.find_by_canonical_key(canonical_key)
        if existing_id and not force_new:
            return self.store.load_project(existing_id)
        reference_id = (
            f"ref-{source_hash[:12]}"
            if not force_new
            else f"ref-{source_hash[:8]}-{uuid.uuid4().hex[:6]}"
        )
        workspace = self.store.create_workspace(reference_id)
        target = workspace / "source" / f"original{source.suffix.lower() or '.mp4'}"
        shutil.copy2(source, target)
        project = ReferenceProject(
            reference_id=reference_id,
            status=ProjectStatus.INGESTED,
            source=SourceDescriptor(
                kind="file",
                platform=Platform.LOCAL,
                original_path=str(source),
                title=title or source.stem,
                source_sha256=source_hash,
                canonical_key=canonical_key,
            ),
            access=SourceAccess(declaration=rights, operator_note=operator_note),
            workspace_path=str(workspace),
        )
        self.store.save_project(project)
        self.store.record_event(
            reference_id,
            stage="ingest",
            status="completed",
            message="Local file copied into the reference workspace.",
            details={"target": str(target), "sha256": source_hash},
        )
        return project

    def ingest_url(
        self,
        url: str,
        *,
        rights: RightsDeclaration,
        title: str | None = None,
        operator_note: str | None = None,
        cookies_from_browser: str | None = None,
        cookie_file: Path | str | None = None,
        force_new: bool = False,
    ) -> ReferenceProject:
        platform = validate_direct_video_url(url)
        local_cookie_browser = validate_local_cookie_browser(cookies_from_browser)
        local_cookie_file = Path(cookie_file).expanduser().resolve() if cookie_file else None
        if local_cookie_file and not local_cookie_file.is_file():
            raise FileNotFoundError(local_cookie_file)
        if local_cookie_browser and local_cookie_file:
            raise ValueError("Use either cookies_from_browser or cookie_file, not both")
        canonical_key = canonical_url_key(url)
        existing_id = self.store.find_by_canonical_key(canonical_key)
        if existing_id and not force_new:
            project = self.store.load_project(existing_id)
            if has_valid_cached_acquisition(project):
                return project
            reference_id = project.reference_id
            workspace = Path(project.workspace_path)
            project.status = ProjectStatus.INGESTING
            project.errors = []
            project.access = SourceAccess(declaration=rights, operator_note=operator_note)
            if title:
                project.source.title = title
        else:
            reference_id = (
                reference_id_from_key(canonical_key)
                if not force_new
                else f"{reference_id_from_key(canonical_key)}-{uuid.uuid4().hex[:6]}"
            )
            workspace = self.store.create_workspace(reference_id)
            project = ReferenceProject(
                reference_id=reference_id,
                status=ProjectStatus.INGESTING,
                source=SourceDescriptor(
                    kind="url",
                    platform=platform,
                    original_url=canonicalize_url(url),
                    title=title or f"{platform.value} reference",
                    canonical_key=canonical_key,
                ),
                access=SourceAccess(declaration=rights, operator_note=operator_note),
                workspace_path=str(workspace),
            )
        self.store.save_project(project)
        try:
            outcome = AcquisitionService().acquire(
                url,
                workspace,
                rights=rights,
                cookies_from_browser=local_cookie_browser,
                cookie_file=local_cookie_file,
            )
            source_file = outcome.primary_path
            metadata = outcome.manifest.metadata
            project.source.source_sha256 = sha256_file(source_file)
            project.source.title = str(metadata.get("title") or project.source.title)
            project.source.uploader = metadata.get("uploader")
            project.status = ProjectStatus.INGESTED
            self.store.save_project(project)
            self.store.record_event(
                reference_id,
                stage="ingest",
                status="completed",
                message="Authorized public URL ingestion completed.",
                details={
                    "platform": platform.value,
                    "source_file": source_file.name,
                    "acquisition_status": outcome.manifest.status.value,
                    "asset_count": len(outcome.manifest.assets),
                    "manifest": "source/acquisition-manifest.json",
                },
            )
            return project
        except Exception as exc:
            sanitized_error = sanitize_diagnostic(
                exc,
                private_paths=[path for path in (local_cookie_file,) if path],
            )
            project.status = ProjectStatus.FAILED
            project.errors.append(sanitized_error)
            self.store.save_project(project)
            self.store.record_event(
                reference_id,
                stage="ingest",
                status="failed",
                message=(
                    "URL ingestion failed. Download the authorized file manually and use "
                    "ingest-file."
                ),
                details={"error": sanitized_error},
            )
            raise
