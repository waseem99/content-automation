"""Typed, resumable operator orchestration for reference-intelligence runs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .acquisition import safe_source_url, sanitize_diagnostic
from .models import ReferenceProject, RightsDeclaration
from .pipeline import ReferencePipeline
from .portfolio_sync import build_portfolio_sync_packet


class ExecutionProfileName(StrEnum):
    CPU = "cpu"
    GPU = "gpu"
    LOW_MEMORY = "low-memory"


class ExecutionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ExecutionProfileName
    transcription_model: str
    transcription_device: str
    local_vision: bool
    every_frame: bool
    description: str
    requirements: list[str]


EXECUTION_PROFILES = {
    ExecutionProfileName.CPU: ExecutionProfile(
        name=ExecutionProfileName.CPU,
        transcription_model="small",
        transcription_device="cpu",
        local_vision=False,
        every_frame=True,
        description="Complete deterministic analysis on a CPU workstation.",
        requirements=["ffmpeg", "ffprobe", "8 GB RAM recommended"],
    ),
    ExecutionProfileName.GPU: ExecutionProfile(
        name=ExecutionProfileName.GPU,
        transcription_model="medium",
        transcription_device="cuda",
        local_vision=True,
        every_frame=True,
        description="Higher-quality local speech and vision observations on a GPU workstation.",
        requirements=["ffmpeg", "ffprobe", "CUDA-capable GPU", "local Ollama vision model"],
    ),
    ExecutionProfileName.LOW_MEMORY: ExecutionProfile(
        name=ExecutionProfileName.LOW_MEMORY,
        transcription_model="tiny",
        transcription_device="cpu",
        local_vision=False,
        every_frame=False,
        description="Reduced-resource deterministic fallback for constrained machines.",
        requirements=["ffmpeg", "ffprobe", "4 GB RAM recommended"],
    ),
}


class ReferenceRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=3000)
    rights: RightsDeclaration
    title: str | None = Field(default=None, max_length=300)
    operator_note: str | None = Field(default=None, max_length=1000)
    brand_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    topic: str | None = Field(default=None, max_length=300)
    force_new: bool = False

    @field_validator("source")
    @classmethod
    def source_must_be_url_or_existing_file(cls, value: str) -> str:
        if value.startswith(("https://", "http://")):
            return value
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError("source must be a public HTTP(S) URL or existing local file")
        return str(path.resolve())


class PortfolioRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.portfolio_run_request.v1"
    profile: ExecutionProfileName = ExecutionProfileName.CPU
    references: list[ReferenceRunInput] = Field(min_length=1, max_length=200)
    continue_on_error: bool = True


class ReferenceRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    source_label: str
    status: str
    reference_id: str | None = None
    platform: str = "unknown"
    media_type: str = "unknown"
    artifact_count: int = 0
    sync_packet: str | None = None
    error_type: str | None = None
    error: str | None = None
    fallback_action: str | None = None
    human_review_required: bool = True
    automatic_publication: bool = False


class PortfolioRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.portfolio_run.v1"
    run_id: str
    profile: ExecutionProfile
    status: str
    attempted: int
    succeeded: int
    failed: int
    results: list[ReferenceRunResult]
    source_media_in_manifest: bool = False
    credentials_in_manifest: bool = False
    automatic_publication: bool = False
    human_review_required: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineProtocol(Protocol):
    def ingest_file(self, source_path: str, **kwargs: Any) -> ReferenceProject: ...

    def ingest_url(self, url: str, **kwargs: Any) -> ReferenceProject: ...

    def process(self, reference_id: str, **kwargs: Any) -> ReferenceProject: ...

    def export_brief(self, reference_id: str, **kwargs: Any) -> Path: ...


def resolve_profile(name: ExecutionProfileName | str) -> ExecutionProfile:
    return EXECUTION_PROFILES[ExecutionProfileName(name)]


def safe_source_label(source: str) -> str:
    if source.startswith(("https://", "http://")):
        return safe_source_url(source)
    path = Path(source)
    digest = hashlib.sha256(path.name.encode()).hexdigest()[:10]
    return f"local-file:{digest}{path.suffix.lower()}"


def safe_run_error(exc: Exception, *, private_paths: list[Path | str]) -> str:
    sanitized = sanitize_diagnostic(exc, private_paths=private_paths)
    return re.sub(r"(?:[A-Za-z]:)?[/\\][^\s'\"]+", "<local-path>", sanitized)[:500]


def run_portfolio(
    request: PortfolioRunRequest,
    workspace: Path,
    *,
    pipeline: PipelineProtocol | None = None,
    cookies_from_browser: str | None = None,
    cookie_file: Path | None = None,
) -> tuple[PortfolioRunManifest, Path]:
    """Process every item independently and write a secret-free run manifest."""
    workspace = workspace.expanduser().resolve()
    engine = pipeline or ReferencePipeline(workspace)
    profile = resolve_profile(request.profile)
    results: list[ReferenceRunResult] = []
    for index, item in enumerate(request.references, start=1):
        try:
            if item.source.startswith(("https://", "http://")):
                project = engine.ingest_url(
                    item.source,
                    rights=item.rights,
                    title=item.title,
                    operator_note=item.operator_note,
                    cookies_from_browser=cookies_from_browser,
                    cookie_file=cookie_file,
                    force_new=item.force_new,
                )
            else:
                project = engine.ingest_file(
                    item.source,
                    rights=item.rights,
                    title=item.title,
                    operator_note=item.operator_note,
                    force_new=item.force_new,
                )
            project = engine.process(
                project.reference_id,
                transcription_model=profile.transcription_model,
                transcription_device=profile.transcription_device,
                use_local_vision=profile.local_vision,
                every_frame=profile.every_frame,
            )
            if item.brand_id:
                engine.export_brief(
                    project.reference_id,
                    brand_id=item.brand_id,
                    topic=item.topic,
                )
            packet = build_portfolio_sync_packet(project, Path(project.workspace_path))
            results.append(
                ReferenceRunResult(
                    index=index,
                    source_label=safe_source_label(item.source),
                    status="succeeded",
                    reference_id=project.reference_id,
                    platform=project.source.platform.value,
                    media_type=packet.media_type,
                    artifact_count=len(packet.artifacts),
                    sync_packet=(
                        f"reference://{project.reference_id}/exports/portfolio_sync_packet.json"
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - isolate every portfolio item
            results.append(
                ReferenceRunResult(
                    index=index,
                    source_label=safe_source_label(item.source),
                    status="failed",
                    error_type=type(exc).__name__,
                    error=safe_run_error(
                        exc,
                        private_paths=[item.source, workspace, cookie_file or ""],
                    ),
                    fallback_action="Use ingest-file with an authorized local export.",
                )
            )
            if not request.continue_on_error:
                break
    succeeded = sum(result.status == "succeeded" for result in results)
    failed = sum(result.status == "failed" for result in results)
    run_suffix = hashlib.sha256(str(len(results)).encode()).hexdigest()[:6]
    run_id = f"portfolio-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{run_suffix}"
    manifest = PortfolioRunManifest(
        run_id=run_id,
        profile=profile,
        status="succeeded" if not failed else "partial" if succeeded else "failed",
        attempted=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
    target = workspace / "portfolio-runs" / run_id / "run-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest, target


def load_portfolio_request(path: Path) -> PortfolioRunRequest:
    return PortfolioRunRequest.model_validate_json(path.read_text(encoding="utf-8"))


def write_request_template(path: Path) -> Path:
    payload = {
        "schema_version": "p75.portfolio_run_request.v1",
        "profile": "cpu",
        "continue_on_error": True,
        "references": [
            {
                "source": "/absolute/path/to/authorized-reference.mp4",
                "rights": "permitted",
                "title": "Reference title",
                "brand_id": "rawr-nation",
                "topic": "A separately researched original topic",
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
