from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", *, timeout_seconds: int = 15) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ComfyUI must use a loopback HTTP endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("ComfyUI endpoint must not contain credentials, query or fragment")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def upload_image(self, path: Path, *, subfolder: str) -> str:
        if not path.is_file() or path.stat().st_size <= 0:
            raise ComfyUIError("comfyui_input_image_missing")
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ComfyUIError("comfyui_input_image_too_large")
        boundary = f"----content-automation-{uuid4().hex}"
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n{subfolder}\r\n".encode(),
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n"
            ).encode(),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        request = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=b"".join(parts),
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout_seconds, 60)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyUIError("comfyui_input_upload_failed") from exc
        name = str(payload.get("name") or "").strip()
        returned_subfolder = str(payload.get("subfolder") or "").strip()
        if not name or returned_subfolder != subfolder:
            raise ComfyUIError("comfyui_input_upload_response_invalid")
        return f"{subfolder}/{name}" if subfolder else name

    def submit(self, workflow: dict[str, Any], *, client_id: str) -> str:
        payload = self._json_request(
            "/prompt",
            method="POST",
            payload={"prompt": workflow, "client_id": client_id},
        )
        prompt_id = str(payload.get("prompt_id") or "").strip()
        if not prompt_id:
            raise ComfyUIError("comfyui_submit_missing_prompt_id")
        return prompt_id

    def wait(self, prompt_id: str, *, timeout_seconds: int, poll_seconds: float = 2.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            history = self._json_request(f"/history/{urllib.parse.quote(prompt_id)}")
            item = history.get(prompt_id)
            if item:
                status = item.get("status") or {}
                if status.get("status_str") == "error" or status.get("completed") is False:
                    messages = status.get("messages") or []
                    if any(message and message[0] == "execution_error" for message in messages):
                        raise ComfyUIError("comfyui_execution_failed")
                if status.get("completed") is True:
                    return item
            time.sleep(max(0.25, min(poll_seconds, 10.0)))
        raise TimeoutError("comfyui_generation_timed_out")

    def cancel(self, prompt_id: str) -> None:
        # Delete only the named queued prompt. Do not call global /interrupt because
        # that could terminate another operator's active generation.
        try:
            self._json_request(
                "/queue",
                method="POST",
                payload={"delete": [prompt_id]},
            )
        except ComfyUIError:
            return

    def first_video_output(self, history_item: dict[str, Any]) -> dict[str, str]:
        for node_output in (history_item.get("outputs") or {}).values():
            for key in ("videos", "gifs", "images"):
                for item in node_output.get(key) or []:
                    filename = str(item.get("filename") or "").strip()
                    if filename.lower().endswith((".mp4", ".webm", ".mov")):
                        return {
                            "filename": filename,
                            "subfolder": str(item.get("subfolder") or ""),
                            "type": str(item.get("type") or "output"),
                        }
        raise ComfyUIError("comfyui_video_output_missing")

    def download_output(self, output: dict[str, str], destination: Path) -> Path:
        params = urllib.parse.urlencode(
            {
                "filename": output["filename"],
                "subfolder": output.get("subfolder", ""),
                "type": output.get("type", "output"),
            }
        )
        request = urllib.request.Request(f"{self.base_url}/view?{params}", method="GET")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout_seconds, 60)) as response:
                content_type = str(response.headers.get("Content-Type") or "").lower()
                if "text/html" in content_type or "application/json" in content_type:
                    raise ComfyUIError("comfyui_output_not_video")
                with destination.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
        except (urllib.error.URLError, OSError) as exc:
            raise ComfyUIError("comfyui_output_download_failed") from exc
        if not destination.is_file() or destination.stat().st_size == 0:
            raise ComfyUIError("comfyui_output_empty")
        return destination

    def _json_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyUIError("comfyui_request_failed") from exc
        if not isinstance(parsed, dict):
            raise ComfyUIError("comfyui_response_invalid")
        return parsed
