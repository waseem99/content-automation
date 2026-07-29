from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.application.local_video.models import LocalVideoJob, LocalVideoJobStatus, LocalVideoRequest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ComfyUILocalVideoProvider:
    name = "local-comfyui-video"
    requires_paid_approval = False

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=120,
            trust_env=False,
        )

    def health(self) -> dict[str, Any]:
        response = self.client.get("/system_stats")
        response.raise_for_status()
        return {
            "healthy": True,
            "provider": self.name,
            "external_fee_possible": False,
            "system_stats": response.json(),
        }

    @staticmethod
    def _replace(value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUILocalVideoProvider._replace(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUILocalVideoProvider._replace(item, replacements) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    def workflow_for(self, request: LocalVideoRequest) -> dict[str, Any]:
        actual_workflow_sha = _sha256(request.workflow_path)
        if actual_workflow_sha != request.workflow_sha256:
            raise RuntimeError("local video workflow hash mismatch")
        workflow = json.loads(request.workflow_path.read_text(encoding="utf-8"))
        replacements = {
            "{{MODEL_KEY}}": request.model_key,
            "{{CHECKPOINT_SHA256}}": request.checkpoint_sha256,
            "{{INPUT_IMAGE_PATH}}": str(request.input_image_path),
            "{{END_IMAGE_PATH}}": str(request.end_image_path) if request.end_image_path else "",
            "{{POSITIVE_PROMPT}}": request.prompt,
            "{{NEGATIVE_PROMPT}}": request.negative_prompt,
            "{{SEED}}": request.seed,
            "{{WIDTH}}": request.width,
            "{{HEIGHT}}": request.height,
            "{{FPS}}": request.fps,
            "{{FRAME_COUNT}}": request.frame_count,
            "{{INFERENCE_STEPS}}": request.inference_steps,
            "{{OUTPUT_PREFIX}}": request.output_prefix,
        }
        return self._replace(workflow, replacements)

    def submit(self, request: LocalVideoRequest) -> LocalVideoJob:
        response = self.client.post(
            "/prompt",
            json={
                "prompt": self.workflow_for(request),
                "client_id": f"p114-video-{request.idempotency_key[:24]}",
            },
            headers={"Idempotency-Key": request.idempotency_key},
        )
        response.raise_for_status()
        prompt_id = str(response.json().get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        return LocalVideoJob(
            provider=self.name,
            provider_job_id=prompt_id,
            idempotency_key=request.idempotency_key,
            status=LocalVideoJobStatus.QUEUED,
            model_key=request.model_key,
            workflow_sha256=request.workflow_sha256,
            submitted_at=_now(),
        )

    def poll(self, job: LocalVideoJob) -> LocalVideoJob:
        response = self.client.get(f"/history/{job.provider_job_id}")
        response.raise_for_status()
        record = response.json().get(job.provider_job_id)
        if not record:
            return LocalVideoJob(**{**job.__dict__, "status": LocalVideoJobStatus.RUNNING})
        status = record.get("status") or {}
        if status.get("status_str") in {"error", "failed"}:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.FAILED,
                    "error": json.dumps(status, default=str)[-4000:],
                }
            )
        descriptor = self._video_descriptor(record)
        if descriptor:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.SUCCEEDED,
                    "output_descriptor": descriptor,
                }
            )
        if status.get("completed") is True:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.FAILED,
                    "error": "ComfyUI completed without an MP4 output",
                }
            )
        return LocalVideoJob(**{**job.__dict__, "status": LocalVideoJobStatus.RUNNING})

    def cancel(self, job: LocalVideoJob) -> LocalVideoJob:
        response = self.client.post("/interrupt")
        response.raise_for_status()
        return LocalVideoJob(**{**job.__dict__, "status": LocalVideoJobStatus.CANCELLED})

    def download(self, job: LocalVideoJob, output_path: Path) -> Path:
        if job.status != LocalVideoJobStatus.SUCCEEDED or not job.output_descriptor:
            raise ValueError("only successful local video jobs can be downloaded")
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial = output_path.with_suffix(output_path.suffix + ".partial")
        partial.write_bytes(response.content)
        if not partial.is_file() or partial.stat().st_size == 0:
            partial.unlink(missing_ok=True)
            raise RuntimeError("downloaded local video is empty")
        if not response.headers.get("content-type", "").lower().startswith("video/") and partial.suffix.lower() != ".mp4.partial":
            partial.unlink(missing_ok=True)
            raise RuntimeError("ComfyUI output is not a video")
        partial.replace(output_path)
        return output_path

    @staticmethod
    def _video_descriptor(record: dict[str, Any]) -> dict[str, Any] | None:
        for node in (record.get("outputs") or {}).values():
            for key in ("videos", "gifs", "images"):
                for item in node.get(key) or []:
                    filename = str(item.get("filename") or "")
                    if filename.lower().endswith((".mp4", ".mov", ".webm")):
                        return item
        return None
