from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .acquisition import AcquisitionManifest, AssetRole
from .analysis import OllamaVisionProvider, analyze_reference
from .fingerprint import create_fingerprint, create_original_brief
from .frame_stream import analyze_every_frame
from .images import ImageReferenceProcessor, OllamaImageObserver, collect_images
from .ingest import IngestionService
from .media import (
    detect_scenes,
    extract_interval_frames,
    find_source_media,
    make_contact_sheet,
    normalize_media,
    resolve_interval_seconds,
    save_frame_manifest,
)
from .models import ProcessingEvent, ProjectStatus, ReferenceProject, RightsDeclaration
from .report import generate_report
from .storage import WorkspaceStore
from .transcript import transcribe_audio


def _version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _binary_version(binary: str) -> str | None:
    path = shutil.which(binary)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        line = (result.stdout or result.stderr).splitlines()[0]
        return line.strip()
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def tool_versions() -> dict[str, str]:
    values = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ffmpeg": _binary_version("ffmpeg"),
        "ffprobe": _binary_version("ffprobe"),
        "yt-dlp": _version("yt-dlp"),
        "pyscenedetect": _version("scenedetect"),
        "faster-whisper": _version("faster-whisper"),
        "playwright": _version("playwright"),
        "pillow": _version("pillow"),
        "pydantic": _version("pydantic"),
    }
    return {key: value for key, value in values.items() if value}


class ReferencePipeline:
    def __init__(self, workspace_root: Path | str = "workspace") -> None:
        self.store = WorkspaceStore(workspace_root)
        self.ingestion = IngestionService(self.store)

    def ingest_file(
        self,
        source_path: Path | str,
        *,
        rights: RightsDeclaration,
        title: str | None = None,
        operator_note: str | None = None,
        force_new: bool = False,
    ) -> ReferenceProject:
        return self.ingestion.ingest_file(
            source_path,
            rights=rights,
            title=title,
            operator_note=operator_note,
            force_new=force_new,
        )

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
        options: dict[str, object] = {
            "rights": rights,
            "title": title,
            "operator_note": operator_note,
            "cookies_from_browser": cookies_from_browser,
            "force_new": force_new,
        }
        if cookie_file is not None:
            options["cookie_file"] = cookie_file
        return self.ingestion.ingest_url(url, **options)

    def _event(
        self,
        project: ReferenceProject,
        stage: str,
        status: str,
        message: str,
        **details: object,
    ) -> None:
        project.events.append(
            ProcessingEvent(
                stage=stage,
                status=status,
                message=message,
                details=details,
            )
        )
        self.store.record_event(
            project.reference_id,
            stage=stage,
            status=status,
            message=message,
            details=details,
        )
        self.store.save_project(project)

    def process(
        self,
        reference_id: str,
        *,
        interval_seconds: int | None = None,
        transcription_model: str = "small",
        transcription_device: str = "auto",
        use_local_vision: bool | None = None,
        every_frame: bool = False,
        force: bool = False,
    ) -> ReferenceProject:
        project = self.store.load_project(reference_id)
        workspace = Path(project.workspace_path)
        project.status = ProjectStatus.PROCESSING
        project.tool_versions = tool_versions()
        self._event(project, "pipeline", "started", "Reference processing started.")
        try:
            try:
                source = find_source_media(workspace)
            except FileNotFoundError as video_error:
                image_paths = self._image_sources(workspace)
                if not image_paths:
                    raise video_error
                image_vision_enabled = (
                    os.getenv("REFINTEL_USE_OLLAMA", "0") == "1"
                    if use_local_vision is None
                    else use_local_vision
                )
                image_observer = (
                    OllamaImageObserver(
                        model=os.getenv("REFINTEL_OLLAMA_MODEL", "qwen2.5vl:7b"),
                        endpoint=os.getenv(
                            "REFINTEL_OLLAMA_ENDPOINT",
                            "http://127.0.0.1:11434/api/chat",
                        ),
                    )
                    if image_vision_enabled
                    else None
                )
                self._event(
                    project,
                    "images",
                    "started",
                    "Processing image or carousel evidence.",
                    asset_count=len(image_paths),
                )
                image_manifest, image_manifest_path = ImageReferenceProcessor(
                    observer=image_observer
                ).process(
                    image_paths,
                    workspace / "image-analysis",
                    rights=project.access.declaration,
                    title=project.source.title,
                    force=force,
                )
                project.status = (
                    ProjectStatus.COMPLETE if image_manifest.slide_count else ProjectStatus.FAILED
                )
                project.updated_at = datetime.now(UTC)
                self._event(
                    project,
                    "images",
                    "completed" if image_manifest.slide_count else "failed",
                    "Image or carousel evidence processing completed.",
                    manifest=str(image_manifest_path.relative_to(workspace)),
                    slide_count=image_manifest.slide_count,
                    failure_count=len(image_manifest.failures),
                )
                self._event(
                    project,
                    "pipeline",
                    "completed" if image_manifest.slide_count else "failed",
                    "Reference processing completed.",
                )
                return project
            proxy_path = workspace / "media" / "analysis.mp4"
            audio_path = workspace / "media" / "audio.wav"
            if force or not proxy_path.exists():
                self._event(project, "media", "started", "Normalizing source media.")
                proxy_path, audio_path, metadata = normalize_media(source, workspace)
                project.media = metadata
                self._event(project, "media", "completed", "Media normalization completed.")
            elif project.media is None:
                _, _, metadata = normalize_media(source, workspace)
                project.media = metadata
            assert project.media is not None

            frame_manifest = workspace / "frames" / "frame_manifest.json"
            if force or not frame_manifest.exists():
                self._event(project, "frames", "started", "Extracting interval and scene frames.")
                resolved_interval, sampling_mode = resolve_interval_seconds(
                    project.media.duration_seconds,
                    interval_seconds,
                )
                interval_frames = extract_interval_frames(
                    proxy_path,
                    workspace,
                    duration_seconds=project.media.duration_seconds,
                    interval_seconds=resolved_interval,
                )
                scenes, scene_frames = detect_scenes(proxy_path, workspace)
                project.frames = interval_frames + scene_frames
                project.scenes = scenes
                save_frame_manifest(
                    workspace,
                    project.frames,
                    project.scenes,
                    sampling={
                        "mode": sampling_mode,
                        "interval_seconds": resolved_interval,
                        "duration_seconds": project.media.duration_seconds,
                        "scene_detection_enabled": True,
                    },
                )
                if project.frames:
                    make_contact_sheet(workspace, project.frames)
                self._event(
                    project,
                    "frames",
                    "completed",
                    "Frame extraction completed.",
                    sampling_mode=sampling_mode,
                    interval_seconds=resolved_interval,
                    frame_count=len(project.frames),
                    scene_count=len(project.scenes),
                )

            every_frame_path = workspace / "frames" / "every_frame_metrics.json"
            if every_frame and (force or not every_frame_path.exists()):
                self._event(
                    project,
                    "every_frame",
                    "started",
                    "Decoding and measuring every source frame.",
                )
                frame_metrics = analyze_every_frame(proxy_path, workspace)
                self._event(
                    project,
                    "every_frame",
                    "completed",
                    "Every-frame motion analysis completed.",
                    frame_count=frame_metrics["frame_count"],
                    candidate_cut_count=frame_metrics["candidate_cut_count"],
                )

            transcript_json = workspace / "transcript" / "transcript.json"
            if force or not transcript_json.exists():
                self._event(project, "transcript", "started", "Generating local transcript.")
                segments, transcript_info = transcribe_audio(
                    audio_path,
                    workspace,
                    model_size=transcription_model,
                    device=transcription_device,
                )
                project.transcript = segments
                self._event(
                    project,
                    "transcript",
                    "completed",
                    "Transcript stage completed.",
                    **transcript_info,
                )

            vision_enabled = (
                os.getenv("REFINTEL_USE_OLLAMA", "0") == "1"
                if use_local_vision is None
                else use_local_vision
            )
            provider = (
                OllamaVisionProvider(
                    model=os.getenv("REFINTEL_OLLAMA_MODEL", "qwen2.5vl:7b"),
                    endpoint=os.getenv(
                        "REFINTEL_OLLAMA_ENDPOINT",
                        "http://127.0.0.1:11434/api/chat",
                    ),
                )
                if vision_enabled
                else None
            )
            self._event(project, "analysis", "started", "Analyzing reference mechanics.")
            project.analysis = analyze_reference(
                workspace=workspace,
                metadata=project.media,
                frames=project.frames,
                scenes=project.scenes,
                transcript=project.transcript,
                visual_provider=provider,
            )
            analysis_path = workspace / "analysis" / "reference_analysis.json"
            analysis_path.write_text(project.analysis.model_dump_json(indent=2), encoding="utf-8")
            self._event(project, "analysis", "completed", "Reference analysis completed.")

            self._event(project, "report", "started", "Generating offline interactive report.")
            report_path = generate_report(project, workspace)
            self._event(
                project,
                "report",
                "completed",
                "Offline interactive report generated.",
                report=str(report_path),
            )

            self._event(project, "fingerprint", "started", "Creating reference fingerprint.")
            create_fingerprint(project, workspace)
            self._event(
                project,
                "fingerprint",
                "completed",
                "Reference fingerprint created.",
            )
            project.status = ProjectStatus.COMPLETE
            project.updated_at = datetime.now(UTC)
            self._event(project, "pipeline", "completed", "Reference processing completed.")
            return project
        except Exception as exc:
            project.status = ProjectStatus.FAILED
            project.errors.append(str(exc))
            self._event(
                project,
                "pipeline",
                "failed",
                "Reference processing failed.",
                error=str(exc),
            )
            raise

    @staticmethod
    def _image_sources(workspace: Path) -> list[Path]:
        manifest_path = workspace / "source" / "acquisition-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = AcquisitionManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                roles = {AssetRole.PRIMARY_IMAGE, AssetRole.CAROUSEL_IMAGE}
                selected = [
                    workspace / asset.relative_path
                    for asset in manifest.assets
                    if asset.role in roles
                ]
                if selected:
                    return collect_images(selected)
            except (ValueError, FileNotFoundError):
                pass
        try:
            return collect_images(workspace / "source")
        except (FileNotFoundError, ValueError):
            return []

    def export_brief(
        self,
        reference_id: str,
        *,
        brand_id: str,
        topic: str | None = None,
        audience: str = "social video viewers interested in surprising, useful stories",
        duration_seconds: int = 60,
    ) -> Path:
        project = self.store.load_project(reference_id)
        workspace = Path(project.workspace_path)
        fingerprint_path = workspace / "exports" / "reference_fingerprint.json"
        if not fingerprint_path.exists():
            raise FileNotFoundError("Process the reference before exporting a brief")
        from .models import ReferenceFingerprint

        fingerprint = ReferenceFingerprint.model_validate_json(
            fingerprint_path.read_text(encoding="utf-8")
        )
        create_original_brief(
            project,
            fingerprint,
            workspace,
            brand_id=brand_id,
            topic=topic,
            audience=audience,
            duration_seconds=duration_seconds,
        )
        return workspace / "exports" / "original_content_brief.json"
