"""Guarded asynchronous ComfyUI video provider for P114 local clips."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


class VideoJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class LocalVideoGenerationRequest:
    job_id: str
    prompt: str
    negative_prompt: str
    seed: int
    width: int
    height: int
    frame_count: int
    fps: int
    inference_steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    input_image: Path
    output_prefix: str
    model_key: str

    @property
    def idempotency_key(self) -> str:
        payload = {
            "job_id": self.job_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "inference_steps": self.inference_steps,
            "cfg": self.cfg,
            "sampler_name": self.sampler_name,
            "scheduler": self.scheduler,
            "input_image_sha256": sha256_file(self.input_image),
            "model_key": self.model_key,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class LocalVideoJob:
    provider: str
    provider_job_id: str
    idempotency_key: str
    status: VideoJobStatus
    submitted_at: str
    model_key: str
    output_descriptor: dict[str, Any] | None = None
    error: str | None = None


class ComfyUIVideoProvider:
    name = "local-comfyui-video"
    requires_paid_approval = False

    def __init__(
        self,
        *,
        base_url: str,
        workflow_path: Path,
        expected_workflow_sha256: str,
        bearer_token: str | None = None,
        client: "httpx.Client | None" = None,
    ) -> None:
        import httpx

        resolved = workflow_path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        actual = sha256_file(resolved)
        if actual != expected_workflow_sha256:
            raise RuntimeError(
                f"ComfyUI workflow hash mismatch: expected {expected_workflow_sha256}, found {actual}"
            )
        parsed = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or not parsed:
            raise RuntimeError("ComfyUI API workflow must be a non-empty JSON object")
        if any(not isinstance(node, dict) or "class_type" not in node for node in parsed.values()):
            raise RuntimeError("ComfyUI workflow is not API prompt format")
        self.workflow_path = resolved
        self.workflow_sha256 = actual
        self._workflow = parsed
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=120,
            trust_env=False,
        )

    def health(self) -> dict[str, Any]:
        response = self.client.get("/system_stats")
        response.raise_for_status()
        return {
            "healthy": True,
            "provider": self.name,
            "workflow_sha256": self.workflow_sha256,
            "system_stats": response.json(),
        }

    @staticmethod
    def _replace(value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUIVideoProvider._replace(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUIVideoProvider._replace(item, replacements) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    def upload_input(self, path: Path, *, remote_name: str) -> str:
        resolved = path.resolve()
        if not resolved.is_file() or resolved.stat().st_size == 0:
            raise RuntimeError("local video input image is missing or empty")
        with resolved.open("rb") as handle:
            response = self.client.post(
                "/upload/image",
                files={"image": (remote_name, handle, "application/octet-stream")},
                data={"overwrite": "true", "type": "input"},
            )
        response.raise_for_status()
        payload = response.json()
        name = str(payload.get("name") or remote_name)
        subfolder = str(payload.get("subfolder") or "")
        return f"{subfolder}/{name}".lstrip("/") if subfolder else name

    def workflow_for(self, request: LocalVideoGenerationRequest, *, uploaded_image: str) -> dict[str, Any]:
        replacements: dict[str, Any] = {
            "{{POSITIVE_PROMPT}}": request.prompt,
            "{{NEGATIVE_PROMPT}}": request.negative_prompt,
            "{{SEED}}": request.seed,
            "{{WIDTH}}": request.width,
            "{{HEIGHT}}": request.height,
            "{{FRAME_COUNT}}": request.frame_count,
            "{{FPS}}": request.fps,
            "{{STEPS}}": request.inference_steps,
            "{{CFG}}": request.cfg,
            "{{SAMPLER_NAME}}": request.sampler_name,
            "{{SCHEDULER}}": request.scheduler,
            "{{INPUT_IMAGE}}": uploaded_image,
            "{{OUTPUT_PREFIX}}": request.output_prefix,
        }
        rendered = self._replace(self._workflow, replacements)
        unresolved = [
            value
            for value in self._walk_strings(rendered)
            if value.startswith("{{") and value.endswith("}}")
        ]
        if unresolved:
            raise RuntimeError(f"unresolved ComfyUI workflow placeholders: {sorted(set(unresolved))}")
        return rendered

    def submit(self, request: LocalVideoGenerationRequest) -> LocalVideoJob:
        uploaded = self.upload_input(
            request.input_image,
            remote_name=f"p114-{request.job_id}-{request.idempotency_key[:12]}{request.input_image.suffix.lower() or '.png'}",
        )
        response = self.client.post(
            "/prompt",
            json={
                "prompt": self.workflow_for(request, uploaded_image=uploaded),
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
            status=VideoJobStatus.QUEUED,
            submitted_at=_now(),
            model_key=request.model_key,
        )

    def poll(self, job: LocalVideoJob) -> LocalVideoJob:
        response = self.client.get(f"/history/{job.provider_job_id}")
        response.raise_for_status()
        record = response.json().get(job.provider_job_id)
        if not record:
            return LocalVideoJob(**{**job.__dict__, "status": VideoJobStatus.RUNNING})
        status = record.get("status") or {}
        if status.get("status_str") in {"error", "failed"}:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": VideoJobStatus.FAILED,
                    "error": json.dumps(status, default=str)[-4000:],
                }
            )
        descriptor = self._find_video_descriptor(record.get("outputs") or {})
        if descriptor is not None:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": VideoJobStatus.SUCCEEDED,
                    "output_descriptor": descriptor,
                }
            )
        if status.get("completed") is True:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": VideoJobStatus.FAILED,
                    "error": "ComfyUI completed without a downloadable video output",
                }
            )
        return LocalVideoJob(**{**job.__dict__, "status": VideoJobStatus.RUNNING})

    def cancel(self, job: LocalVideoJob) -> None:
        try:
            self.client.post("/queue", json={"delete": [job.provider_job_id]}).raise_for_status()
        except Exception:
            pass
        try:
            self.client.post("/interrupt", json={}).raise_for_status()
        except Exception:
            pass

    def download(self, job: LocalVideoJob, output_path: Path) -> Path:
        if job.status != VideoJobStatus.SUCCEEDED or not job.output_descriptor:
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
        suffix = Path(str(descriptor["filename"])).suffix.lower() or ".mp4"
        final = output_path.with_suffix(suffix)
        partial = final.with_suffix(f"{suffix}.partial")
        partial.write_bytes(response.content)
        if not partial.is_file() or partial.stat().st_size == 0:
            partial.unlink(missing_ok=True)
            raise RuntimeError("downloaded ComfyUI video is empty")
        partial.replace(final)
        return final

    @staticmethod
    def _find_video_descriptor(outputs: dict[str, Any]) -> dict[str, Any] | None:
        for node in outputs.values():
            for key in ("videos", "gifs", "images"):
                for item in node.get(key) or []:
                    filename = str(item.get("filename") or "")
                    if filename and Path(filename).suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
                        return dict(item)
        return None

    @staticmethod
    def _walk_strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from ComfyUIVideoProvider._walk_strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from ComfyUIVideoProvider._walk_strings(item)
