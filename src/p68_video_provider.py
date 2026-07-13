"""Provider-neutral asynchronous video generation for P68 shots."""

from __future__ import annotations

import hashlib
import json
import math
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import httpx


class VideoJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class VideoGenerationRequest:
    pilot_id: str
    shot_id: str
    input_image: Path
    prompt: str
    negative_prompt: str
    duration_seconds: float
    seed: int
    width: int = 704
    height: int = 1280
    fps: int = 24
    model_id: str = "wan2.2-ti2v-5b"
    output_prefix: str = "p68"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.input_image.is_file():
            raise FileNotFoundError(self.input_image)
        if not self.pilot_id or not self.shot_id:
            raise ValueError("pilot_id and shot_id are required")
        if not self.prompt.strip():
            raise ValueError("A motion prompt is required")
        if self.duration_seconds <= 0 or self.fps <= 0:
            raise ValueError("duration_seconds and fps must be positive")
        if self.width > self.height:
            raise ValueError("P68 generation inputs must be portrait")

    @property
    def frame_count(self) -> int:
        # Wan video latent lengths are 4n+1. Round upward so transition handles
        # are never shorter than the assembly plan requires.
        target = self.duration_seconds * self.fps
        return int(math.ceil(max(target - 1, 0) / 4) * 4 + 1)

    @property
    def input_sha256(self) -> str:
        return _sha256(self.input_image)

    @property
    def idempotency_key(self) -> str:
        payload = {
            "pilot_id": self.pilot_id,
            "shot_id": self.shot_id,
            "input_sha256": self.input_sha256,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "duration_seconds": self.duration_seconds,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "model_id": self.model_id,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class VideoJob:
    provider: str
    provider_job_id: str
    idempotency_key: str
    status: VideoJobStatus
    submitted_at: str
    model_id: str
    output_descriptor: dict[str, Any] | None = None
    error: str | None = None


class VideoProvider(Protocol):
    name: str
    requires_paid_approval: bool

    def health(self) -> dict[str, Any]: ...

    def submit(self, request: VideoGenerationRequest) -> VideoJob: ...

    def poll(self, job: VideoJob) -> VideoJob: ...

    def download(self, job: VideoJob, output_path: Path) -> Path: ...

    def cancel(self, job: VideoJob) -> VideoJob: ...


class ComfyUIVideoProvider:
    """Headless ComfyUI REST adapter suitable for an RN GPU worker."""

    name = "rn-comfyui-wan"
    requires_paid_approval = False

    def __init__(
        self,
        *,
        base_url: str,
        workflow_path: Path,
        bearer_token: str | None = None,
        timeout_seconds: float = 60,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.timeout_seconds = timeout_seconds
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self.client = client or httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout_seconds,
            trust_env=False,
        )
        if not workflow_path.is_file():
            raise FileNotFoundError(workflow_path)

    def health(self) -> dict[str, Any]:
        response = self.client.get("/system_stats")
        response.raise_for_status()
        payload = response.json()
        return {"healthy": True, "provider": self.name, "system_stats": payload}

    def _upload(self, path: Path, remote_name: str) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            response = self.client.post(
                "/upload/image",
                data={"type": "input", "overwrite": "true"},
                files={"image": (remote_name, handle, mime)},
            )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("name") or remote_name)

    @staticmethod
    def _replace(value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUIVideoProvider._replace(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUIVideoProvider._replace(item, replacements) for item in value]
        if isinstance(value, str):
            if value in replacements:
                return replacements[value]
            result = value
            for token, replacement in replacements.items():
                result = result.replace(token, str(replacement))
            return result
        return value

    def workflow_for(self, request: VideoGenerationRequest, uploaded_name: str) -> dict[str, Any]:
        workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        replacements: dict[str, Any] = {
            "{{INPUT_IMAGE}}": uploaded_name,
            "{{POSITIVE_PROMPT}}": request.prompt,
            "{{NEGATIVE_PROMPT}}": request.negative_prompt,
            "{{SEED}}": request.seed,
            "{{WIDTH}}": request.width,
            "{{HEIGHT}}": request.height,
            "{{FRAME_COUNT}}": request.frame_count,
            "{{FPS}}": request.fps,
            "{{OUTPUT_PREFIX}}": f"{request.output_prefix}/{request.pilot_id}-{request.shot_id}",
        }
        rendered = self._replace(workflow, replacements)
        if not isinstance(rendered, dict) or not rendered:
            raise ValueError("ComfyUI API workflow must be a non-empty object")
        return rendered

    def submit(self, request: VideoGenerationRequest) -> VideoJob:
        remote_name = f"{request.idempotency_key[:16]}-{request.input_image.name}"
        uploaded = self._upload(request.input_image, remote_name)
        workflow = self.workflow_for(request, uploaded)
        response = self.client.post(
            "/prompt",
            json={"prompt": workflow, "client_id": f"p68-{request.idempotency_key[:24]}"},
            headers={"Idempotency-Key": request.idempotency_key},
        )
        response.raise_for_status()
        payload = response.json()
        prompt_id = str(payload.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {payload}")
        return VideoJob(
            provider=self.name,
            provider_job_id=prompt_id,
            idempotency_key=request.idempotency_key,
            status=VideoJobStatus.QUEUED,
            submitted_at=_utc_now(),
            model_id=request.model_id,
        )

    @staticmethod
    def _find_output(outputs: dict[str, Any]) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for node in outputs.values():
            for key in ("videos", "gifs", "images"):
                for item in node.get(key) or []:
                    if isinstance(item, dict) and item.get("filename"):
                        candidates.append(item)
        return next(
            (item for item in candidates if Path(str(item["filename"])).suffix.lower() in {".mp4", ".webm", ".mov"}),
            None,
        )

    def poll(self, job: VideoJob) -> VideoJob:
        response = self.client.get(f"/history/{job.provider_job_id}")
        response.raise_for_status()
        payload = response.json()
        record = payload.get(job.provider_job_id)
        if not record:
            return VideoJob(**{**job.__dict__, "status": VideoJobStatus.RUNNING})
        status = record.get("status") or {}
        messages = status.get("messages") or []
        message_types = {
            str(message[0])
            for message in messages
            if isinstance(message, (list, tuple)) and message
        }
        if status.get("status_str") in {"error", "failed"} or "execution_error" in message_types:
            return VideoJob(
                **{
                    **job.__dict__,
                    "status": VideoJobStatus.FAILED,
                    "error": json.dumps(messages)[-2000:],
                }
            )
        output = self._find_output(record.get("outputs") or {})
        if output:
            return VideoJob(**{**job.__dict__, "status": VideoJobStatus.SUCCEEDED, "output_descriptor": output})
        if status.get("completed") is True:
            return VideoJob(
                **{
                    **job.__dict__,
                    "status": VideoJobStatus.FAILED,
                    "error": "ComfyUI completed without a supported video output",
                }
            )
        return VideoJob(**{**job.__dict__, "status": VideoJobStatus.RUNNING})

    def download(self, job: VideoJob, output_path: Path) -> Path:
        if job.status != VideoJobStatus.SUCCEEDED or not job.output_descriptor:
            raise ValueError("Only successful jobs with an output descriptor can be downloaded")
        descriptor = job.output_descriptor
        response = self.client.get(
            "/view",
            params={
                "filename": descriptor["filename"],
                "subfolder": descriptor.get("subfolder") or "",
                "type": descriptor.get("type") or "output",
            },
        )
        response.raise_for_status()
        suffix = Path(str(descriptor["filename"])).suffix or ".webm"
        target = output_path if output_path.suffix else output_path.with_suffix(suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.stem}.partial{target.suffix}")
        partial.unlink(missing_ok=True)
        try:
            partial.write_bytes(response.content)
            if not partial.stat().st_size:
                raise RuntimeError("Downloaded video is empty")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        return target

    def cancel(self, job: VideoJob) -> VideoJob:
        response = self.client.post("/queue", json={"delete": [job.provider_job_id]})
        response.raise_for_status()
        return VideoJob(**{**job.__dict__, "status": VideoJobStatus.CANCELLED})
