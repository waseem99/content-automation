"""Provider-neutral asynchronous image generation for P68 keyframes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import httpx


class ImageJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class KeyframeGenerationRequest:
    pilot_id: str
    shot_id: str
    prompt: str
    negative_prompt: str
    seed: int
    width: int = 1024
    height: int = 1824
    model_id: str = "local-comfyui-keyframe"

    def __post_init__(self) -> None:
        if not self.pilot_id or not self.shot_id or not self.prompt.strip():
            raise ValueError("pilot_id, shot_id, and prompt are required")
        if self.width >= self.height or self.width < 704 or self.height < 1280:
            raise ValueError("keyframe generation must use a production-sized portrait canvas")

    @property
    def idempotency_key(self) -> str:
        payload = {
            "pilot_id": self.pilot_id, "shot_id": self.shot_id, "prompt": self.prompt,
            "negative_prompt": self.negative_prompt, "seed": self.seed, "width": self.width,
            "height": self.height, "model_id": self.model_id,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ImageJob:
    provider: str
    provider_job_id: str
    idempotency_key: str
    status: ImageJobStatus
    submitted_at: str
    model_id: str
    output_descriptor: dict[str, Any] | None = None
    error: str | None = None


class KeyframeProvider(Protocol):
    name: str
    requires_paid_approval: bool

    def health(self) -> dict[str, Any]: ...
    def submit(self, request: KeyframeGenerationRequest) -> ImageJob: ...
    def poll(self, job: ImageJob) -> ImageJob: ...
    def download(self, job: ImageJob, output_path: Path) -> Path: ...


class ComfyUIKeyframeProvider:
    name = "local-comfyui-keyframe"
    requires_paid_approval = False

    def __init__(self, *, base_url: str, workflow_path: Path, checkpoint: str, bearer_token: str | None = None, client: "httpx.Client | None" = None) -> None:
        import httpx

        if not workflow_path.is_file():
            raise FileNotFoundError(workflow_path)
        self.workflow_path = workflow_path
        self.checkpoint = checkpoint
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=60, trust_env=False)

    def health(self) -> dict[str, Any]:
        response = self.client.get("/system_stats")
        response.raise_for_status()
        return {"healthy": True, "provider": self.name, "system_stats": response.json()}

    @staticmethod
    def _replace(value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUIKeyframeProvider._replace(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUIKeyframeProvider._replace(item, replacements) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    def workflow_for(self, request: KeyframeGenerationRequest) -> dict[str, Any]:
        workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        return self._replace(workflow, {
            "{{CHECKPOINT}}": self.checkpoint, "{{POSITIVE_PROMPT}}": request.prompt,
            "{{NEGATIVE_PROMPT}}": request.negative_prompt, "{{SEED}}": request.seed,
            "{{WIDTH}}": request.width, "{{HEIGHT}}": request.height,
            "{{OUTPUT_PREFIX}}": f"p68-keyframes/{request.pilot_id}-{request.shot_id}",
        })

    def submit(self, request: KeyframeGenerationRequest) -> ImageJob:
        response = self.client.post(
            "/prompt",
            json={"prompt": self.workflow_for(request), "client_id": f"p68-kf-{request.idempotency_key[:24]}"},
            headers={"Idempotency-Key": request.idempotency_key},
        )
        response.raise_for_status()
        prompt_id = str(response.json().get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        return ImageJob(self.name, prompt_id, request.idempotency_key, ImageJobStatus.QUEUED, _now(), request.model_id)

    def poll(self, job: ImageJob) -> ImageJob:
        response = self.client.get(f"/history/{job.provider_job_id}")
        response.raise_for_status()
        record = response.json().get(job.provider_job_id)
        if not record:
            return ImageJob(**{**job.__dict__, "status": ImageJobStatus.RUNNING})
        status = record.get("status") or {}
        if status.get("status_str") in {"error", "failed"}:
            return ImageJob(**{**job.__dict__, "status": ImageJobStatus.FAILED, "error": json.dumps(status)[-2000:]})
        for node in (record.get("outputs") or {}).values():
            for item in node.get("images") or []:
                if item.get("filename"):
                    return ImageJob(**{**job.__dict__, "status": ImageJobStatus.SUCCEEDED, "output_descriptor": item})
        if status.get("completed") is True:
            return ImageJob(**{**job.__dict__, "status": ImageJobStatus.FAILED, "error": "No image output"})
        return ImageJob(**{**job.__dict__, "status": ImageJobStatus.RUNNING})

    def download(self, job: ImageJob, output_path: Path) -> Path:
        if job.status != ImageJobStatus.SUCCEEDED or not job.output_descriptor:
            raise ValueError("Only successful jobs can be downloaded")
        descriptor = job.output_descriptor
        response = self.client.get("/view", params={
            "filename": descriptor["filename"], "subfolder": descriptor.get("subfolder") or "",
            "type": descriptor.get("type") or "output",
        })
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial = output_path.with_suffix(".partial.png")
        partial.write_bytes(response.content)
        if not partial.stat().st_size:
            partial.unlink(missing_ok=True)
            raise RuntimeError("Downloaded keyframe is empty")
        partial.replace(output_path)
        return output_path
