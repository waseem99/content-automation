from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("local ComfyUI must use a loopback HTTP endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("local ComfyUI endpoint must not contain credentials, query or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("local ComfyUI endpoint must not contain a path")
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

    def object_info(self) -> dict[str, Any]:
        response = self.client.get("/object_info")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("ComfyUI object_info response is invalid")
        return payload

    def validate_nodes(self, required_nodes: set[str]) -> dict[str, Any]:
        available = set(self.object_info())
        missing = sorted(required_nodes - available)
        if missing:
            raise RuntimeError("ComfyUI is missing required workflow nodes: " + ",".join(missing))
        return {"ok": True, "required_nodes": sorted(required_nodes), "missing_nodes": []}

    @staticmethod
    def _replace(value: Any, replacements: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUILocalVideoProvider._replace(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUILocalVideoProvider._replace(item, replacements) for item in value]
        if isinstance(value, str):
            if value in replacements:
                return replacements[value]
            rendered = value
            for token, replacement in replacements.items():
                rendered = rendered.replace(token, str(replacement))
            return rendered
        return value

    @staticmethod
    def _remote_image_name(path: Path, prefix: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-.") or "image"
        suffix = path.suffix.lower() if path.suffix else ".png"
        if not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", suffix):
            suffix = ".png"
        return f"{prefix}-{stem}{suffix}"

    def _upload_image(self, path: Path, remote_name: str) -> str:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            response = self.client.post(
                "/upload/image",
                data={"type": "input", "overwrite": "true"},
                files={"image": (remote_name, handle, mime_type)},
            )
        response.raise_for_status()
        payload = response.json()
        uploaded_name = str(payload.get("name") or remote_name).strip()
        if not uploaded_name or "/" in uploaded_name or "\\" in uploaded_name:
            raise RuntimeError("ComfyUI returned an invalid uploaded image name")
        return uploaded_name

    def workflow_for(
        self,
        request: LocalVideoRequest,
        *,
        uploaded_input_name: str | None = None,
        uploaded_end_name: str | None = None,
    ) -> dict[str, Any]:
        actual_workflow_sha = _sha256(request.workflow_path)
        if actual_workflow_sha != request.workflow_sha256:
            raise RuntimeError("local video workflow hash mismatch")
        workflow = json.loads(request.workflow_path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict) or not workflow:
            raise RuntimeError("local video workflow must be a non-empty ComfyUI API object")
        replacements = {
            "{{MODEL_KEY}}": request.model_key,
            "{{CHECKPOINT_SHA256}}": request.checkpoint_sha256,
            "{{INPUT_IMAGE}}": uploaded_input_name or request.input_image_path.name,
            "{{INPUT_IMAGE_PATH}}": uploaded_input_name or request.input_image_path.name,
            "{{END_IMAGE}}": uploaded_end_name or "",
            "{{END_IMAGE_PATH}}": uploaded_end_name or "",
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
        rendered = self._replace(workflow, replacements)
        unresolved = sorted(
            set(re.findall(r"\{\{[A-Z0-9_]+\}\}", json.dumps(rendered, sort_keys=True)))
        )
        if unresolved:
            raise RuntimeError("local video workflow contains unresolved tokens: " + ",".join(unresolved))
        for node_id, node in rendered.items():
            if not isinstance(node, dict) or not node.get("class_type") or not isinstance(node.get("inputs"), dict):
                raise RuntimeError(f"local video workflow node {node_id} is not API format")
        return rendered

    def submit(self, request: LocalVideoRequest) -> LocalVideoJob:
        input_name = self._upload_image(
            request.input_image_path,
            self._remote_image_name(
                request.input_image_path,
                f"p114-{request.idempotency_key[:20]}",
            ),
        )
        end_name = None
        if request.end_image_path is not None:
            end_name = self._upload_image(
                request.end_image_path,
                self._remote_image_name(
                    request.end_image_path,
                    f"p114-end-{request.idempotency_key[:16]}",
                ),
            )
        response = self.client.post(
            "/prompt",
            json={
                "prompt": self.workflow_for(
                    request,
                    uploaded_input_name=input_name,
                    uploaded_end_name=end_name,
                ),
                "client_id": f"p114-video-{request.idempotency_key[:24]}",
            },
            headers={"Idempotency-Key": request.idempotency_key},
        )
        response.raise_for_status()
        payload = response.json()
        prompt_id = str(payload.get("prompt_id") or "")
        if not prompt_id:
            node_errors = payload.get("node_errors") or payload.get("error") or payload
            raise RuntimeError(
                "ComfyUI rejected the local video workflow: "
                + json.dumps(node_errors, default=str, sort_keys=True)[-4000:]
            )
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
        metrics = self._execution_metrics(status)
        messages = status.get("messages") or []
        message_types = {
            str(message[0])
            for message in messages
            if isinstance(message, (list, tuple)) and message
        }
        if status.get("status_str") in {"error", "failed"} or "execution_error" in message_types:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.FAILED,
                    "error": json.dumps(status, default=str)[-4000:],
                    "metrics": metrics,
                }
            )
        descriptor = self._video_descriptor(record)
        if descriptor:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.SUCCEEDED,
                    "output_descriptor": descriptor,
                    "metrics": metrics,
                }
            )
        if status.get("completed") is True:
            return LocalVideoJob(
                **{
                    **job.__dict__,
                    "status": LocalVideoJobStatus.FAILED,
                    "error": "ComfyUI completed without an MP4 output",
                    "metrics": metrics,
                }
            )
        return LocalVideoJob(**{**job.__dict__, "status": LocalVideoJobStatus.RUNNING})

    def cancel(self, job: LocalVideoJob) -> LocalVideoJob:
        response = self.client.post("/queue", json={"delete": [job.provider_job_id]})
        response.raise_for_status()
        return LocalVideoJob(**{**job.__dict__, "status": LocalVideoJobStatus.CANCELLED})

    def download(self, job: LocalVideoJob, output_path: Path) -> Path:
        if job.status != LocalVideoJobStatus.SUCCEEDED or not job.output_descriptor:
            raise ValueError("only successful local video jobs can be downloaded")
        descriptor = job.output_descriptor
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial = output_path.with_suffix(output_path.suffix + ".partial")
        partial.unlink(missing_ok=True)
        try:
            with self.client.stream(
                "GET",
                "/view",
                params={
                    "filename": descriptor["filename"],
                    "subfolder": descriptor.get("subfolder") or "",
                    "type": descriptor.get("type") or "output",
                },
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type not in {"video/mp4", "application/octet-stream"}:
                    raise RuntimeError("ComfyUI output is not an MP4")
                with partial.open("wb") as handle:
                    for block in response.iter_bytes(1024 * 1024):
                        if block:
                            handle.write(block)
            if not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError("downloaded local video is empty")
            partial.replace(output_path)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return output_path

    @staticmethod
    def _execution_metrics(status: dict[str, Any]) -> dict[str, Any]:
        timestamps: dict[str, int] = {}
        for message in status.get("messages") or []:
            if not isinstance(message, (list, tuple)) or len(message) < 2:
                continue
            kind = str(message[0])
            payload = message[1] if isinstance(message[1], dict) else {}
            value = payload.get("timestamp")
            if isinstance(value, (int, float)):
                timestamps[kind] = int(value)
        started = timestamps.get("execution_start")
        completed = timestamps.get("execution_success") or timestamps.get("execution_error")
        active_ms = max(0, completed - started) if started is not None and completed is not None else None
        return {
            "execution_started_at_ms": started,
            "execution_completed_at_ms": completed,
            "gpu_active_ms": active_ms,
            "measurement": "comfyui_execution_messages",
        }

    @staticmethod
    def _video_descriptor(record: dict[str, Any]) -> dict[str, Any] | None:
        for node in (record.get("outputs") or {}).values():
            for key in ("videos", "gifs", "images"):
                for item in node.get(key) or []:
                    filename = str(item.get("filename") or "")
                    if filename.lower().endswith(".mp4"):
                        return item
        return None
