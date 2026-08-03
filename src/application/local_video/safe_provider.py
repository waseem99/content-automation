from __future__ import annotations

import json

import httpx

from src.application.local_video.models import LocalVideoRequest
from src.application.local_video.provider import ComfyUILocalVideoProvider as BaseComfyUILocalVideoProvider


class ComfyUILocalVideoProvider(BaseComfyUILocalVideoProvider):
    """Canonical provider wrapper that preserves ComfyUI validation details."""

    def submit(self, request: LocalVideoRequest):  # type: ignore[override]
        try:
            return super().submit(request)
        except httpx.HTTPStatusError as exc:
            response = exc.response
            try:
                body = response.json()
            except Exception:
                body = response.text[-8000:]
            raise RuntimeError(
                "ComfyUI rejected the local video prompt "
                f"with HTTP {response.status_code}: "
                + json.dumps(body, default=str, sort_keys=True)[-8000:]
            ) from exc
