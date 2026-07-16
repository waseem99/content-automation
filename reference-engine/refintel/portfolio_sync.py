from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

from .models import ReferenceProject


class SyncArtifact(BaseModel):
    artifact_kind: str
    local_locator: str
    sha256: str
    mime_type: str
    summary: dict[str, Any] = Field(default_factory=dict)
    contains_source_media: bool = False
    review_safe: bool = True


class PortfolioSyncPacket(BaseModel):
    schema_version: str = "p75.portfolio_sync_packet.v1"
    local_reference_id: str
    source_locator_hash: str
    source_url: str | None = None
    title: str
    platform: str
    media_type: str
    rights_declaration: str
    status: str
    progress_percent: int = Field(ge=0, le=100)
    artifacts: list[SyncArtifact]
    approval_gates: dict[str, str]
    limitations: list[str] = Field(default_factory=list)
    source_media_included: bool = False
    absolute_local_paths_included: bool = False
    credentials_included: bool = False
    automatic_generation: bool = False
    automatic_publication: bool = False
    human_review_required: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


ARTIFACT_PATHS = {
    "contact_sheet": "frames/contact_sheet.jpg",
    "analysis_report": "reports/index.html",
    "temporal_report": "analysis/temporal_report.json",
    "fingerprint": "exports/reference_fingerprint.json",
}
SENSITIVE_QUERY_PARTS = {
    "auth",
    "authorization",
    "cookie",
    "expires",
    "key",
    "password",
    "secret",
    "session",
    "signature",
    "token",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_url(value: object) -> str | None:
    if not value:
        return None
    parsed = urlsplit(str(value))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not any(part in key.lower() for part in SENSITIVE_QUERY_PARTS)
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.hostname.lower(),
            re.sub(r"/{2,}", "/", parsed.path) or "/",
            urlencode(query),
            "",
        )
    )


def _safe_diagnostic(value: str) -> str:
    sanitized = re.sub(
        r"(?i)(password|secret|token|cookie|authorization)\s*[=:]\s*\S+",
        r"\1=<redacted>",
        value,
    )
    return re.sub(r"(?:[A-Za-z]:)?[/\\][^\s]+", "<local-path>", sanitized)[:500]


def _summary(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".json":
        return {"size_bytes": path.stat().st_size}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"size_bytes": path.stat().st_size, "parse_status": "unavailable"}
    if not isinstance(payload, dict):
        return {"size_bytes": path.stat().st_size, "parse_status": "non_object"}
    allowed = {
        "schema_version",
        "status",
        "reference_id",
        "duration_seconds",
        "human_review_required",
        "ready_for_human_review",
    }
    return {key: payload[key] for key in allowed if key in payload}


def _media_type(project: ReferenceProject) -> str:
    if project.media:
        return "video"
    source = Path(project.workspace_path) / "source"
    image_count = sum(
        path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        for path in source.glob("*")
    )
    return "carousel" if image_count > 1 else "image" if image_count == 1 else "unknown"


def _status(project: ReferenceProject) -> tuple[str, int]:
    mappings = {
        "created": ("queued", 0),
        "ingesting": ("running", 10),
        "ingested": ("queued", 20),
        "processing": ("running", 50),
        "complete": ("succeeded", 100),
        "failed": ("failed", 100),
    }
    return mappings.get(project.status.value, ("partial", 50))


def build_portfolio_sync_packet(
    project: ReferenceProject,
    workspace: Path,
) -> PortfolioSyncPacket:
    artifacts: list[SyncArtifact] = []
    for kind, relative in ARTIFACT_PATHS.items():
        path = workspace / relative
        if not path.is_file():
            continue
        artifacts.append(
            SyncArtifact(
                artifact_kind=kind,
                local_locator=f"reference://{project.reference_id}/{relative}",
                sha256=_sha256(path),
                mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                summary=_summary(path),
            )
        )
    safe_url = _safe_url(project.source.original_url)
    locator = f"{project.reference_id}\n{safe_url or project.source.canonical_key}"
    job_status, progress = _status(project)
    limitations = [_safe_diagnostic(error) for error in project.errors]
    if not artifacts:
        limitations.append("No review-safe artifacts are available yet.")
    if project.source.original_url and not safe_url:
        limitations.append(
            "Source URL was omitted because it was not a safe public HTTP(S) locator."
        )
    packet = PortfolioSyncPacket(
        local_reference_id=project.reference_id,
        source_locator_hash=hashlib.sha256(locator.encode()).hexdigest(),
        source_url=safe_url,
        title=project.source.title,
        platform=project.source.platform.value,
        media_type=_media_type(project),
        rights_declaration=project.access.declaration.value,
        status=job_status,
        progress_percent=progress,
        artifacts=artifacts,
        approval_gates={
            "rights": "pending_human_review",
            "originality": "pending_human_review",
            "editorial": "pending_human_review",
        },
        limitations=limitations,
    )
    target = workspace / "exports" / "portfolio_sync_packet.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(packet.model_dump_json(indent=2), encoding="utf-8")
    return packet
