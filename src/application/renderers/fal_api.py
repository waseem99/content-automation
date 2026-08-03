from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Mapping

from src.application.renderers.provider_http import (
    ManagedHttpAdapter,
    ManagedProviderError,
    ManagedProviderState,
)


class FalQueueRendererAdapter(ManagedHttpAdapter):
    """Official fal queue adapter for reviewed image-to-video requests."""

    provider_key = "fal"
    default_model_key = "fal-ai/wan/v2.2-5b/image-to-video"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        queue_base_url: str | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self.api_key = (api_key or os.getenv("FAL_KEY", "")).strip()
        if not self.api_key:
            raise ManagedProviderError(
                "fal_api_key_missing",
                "FAL_KEY is required in the worker environment.",
            )
        self.queue_base_url = (
            queue_base_url or os.getenv("FAL_QUEUE_BASE_URL", "https://queue.fal.run")
        ).rstrip("/")
        if not self.queue_base_url.startswith("https://"):
            raise ManagedProviderError(
                "fal_queue_url_invalid",
                "The fal queue base URL must use HTTPS.",
            )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit(
        self,
        *,
        model_key: str,
        request_payload: Mapping[str, Any],
        input_paths: list[Path],
    ) -> ManagedProviderState:
        endpoint = self._model_key(model_key)
        if len(input_paths) != 1:
            raise ManagedProviderError(
                "fal_single_image_required",
                "fal Wan image-to-video requires exactly one reviewed input image.",
            )
        metadata = dict(request_payload.get("request_metadata") or {})
        prompt = str(
            metadata.get("approved_prompt")
            or metadata.get("prompt")
            or request_payload.get("prompt")
            or ""
        ).strip()
        if not prompt:
            raise ManagedProviderError(
                "fal_prompt_missing",
                "The managed route has no reviewed fal prompt.",
            )
        fps = max(4, min(60, int(request_payload.get("fps") or metadata.get("fps") or 24)))
        duration = max(1.0, min(5.0, float(request_payload.get("duration_seconds") or 5)))
        requested_frames = int(metadata.get("num_frames") or round(duration * fps) + 1)
        num_frames = max(17, min(161, requested_frames))
        arguments: dict[str, Any] = {
            "image_url": self.data_uri(input_paths[0]),
            "prompt": prompt,
            "num_frames": num_frames,
            "frames_per_second": fps,
            "resolution": str(metadata.get("resolution") or "720p"),
            "aspect_ratio": str(metadata.get("aspect_ratio") or "auto"),
            "enable_safety_checker": bool(metadata.get("enable_safety_checker", True)),
            "enable_output_safety_checker": bool(
                metadata.get("enable_output_safety_checker", True)
            ),
            "enable_prompt_expansion": bool(metadata.get("enable_prompt_expansion", False)),
            "video_quality": str(metadata.get("video_quality") or "high"),
            "video_write_mode": str(metadata.get("video_write_mode") or "balanced"),
            "adjust_fps_for_interpolation": False,
            "num_interpolated_frames": int(metadata.get("num_interpolated_frames") or 0),
        }
        optional = {
            "negative_prompt": metadata.get("negative_prompt"),
            "seed": metadata.get("seed"),
            "num_inference_steps": metadata.get("num_inference_steps"),
            "guidance_scale": metadata.get("guidance_scale"),
            "shift": metadata.get("shift"),
            "interpolator_model": metadata.get("interpolator_model"),
        }
        arguments.update({key: value for key, value in optional.items() if value is not None})
        response = self._json_request(
            "POST",
            f"{self.queue_base_url}/{endpoint}",
            headers=self.headers,
            payload=arguments,
            timeout=max(self.timeout_seconds, 180),
        )
        request_id = self._first_text(response, ("request_id", "requestId", "id"))
        if not request_id:
            raise ManagedProviderError(
                "fal_request_id_missing",
                "fal accepted the request without returning a request ID.",
                retryable=True,
            )
        return ManagedProviderState(
            provider_job_id=request_id,
            status="running",
            payload=response,
        )

    def poll(self, provider_job_id: str, *, model_key: str) -> ManagedProviderState:
        endpoint = self._model_key(model_key)
        base = f"{self.queue_base_url}/{endpoint}/requests/{provider_job_id}"
        status_payload = self._json_request(
            "GET",
            f"{base}/status",
            headers=self.headers,
        )
        raw_status = (
            self._first_text(status_payload, ("status", "state")) or "unknown"
        ).strip().lower().replace("-", "_")
        if raw_status in {"completed", "complete", "success", "succeeded", "done"}:
            result = self._json_request("GET", base, headers=self.headers)
            output_url = self._first_url(result.get("video") or result)
            if not output_url:
                raise ManagedProviderError(
                    "fal_output_url_missing",
                    "fal completed the request without a downloadable video URL.",
                    retryable=True,
                )
            cost = self._decimal(
                result,
                ("actual_cost_usd", "cost_usd", "usd_cost", "total_cost_usd"),
            )
            return ManagedProviderState(
                provider_job_id=provider_job_id,
                status="succeeded",
                payload=result,
                output_url=output_url,
                actual_cost_usd=cost,
            )
        if raw_status in {"failed", "error", "rejected"}:
            return ManagedProviderState(
                provider_job_id=provider_job_id,
                status="failed",
                payload=status_payload,
                actual_cost_usd=self._decimal(
                    status_payload,
                    ("actual_cost_usd", "cost_usd", "usd_cost", "total_cost_usd"),
                ),
                error=self._first_text(status_payload, ("error", "message", "detail")),
            )
        if raw_status in {"cancelled", "canceled"}:
            return ManagedProviderState(
                provider_job_id=provider_job_id,
                status="cancelled",
                payload=status_payload,
            )
        return ManagedProviderState(
            provider_job_id=provider_job_id,
            status="running",
            payload=status_payload,
        )

    def wait(
        self,
        provider_job_id: str,
        *,
        model_key: str,
        timeout_seconds: int,
        poll_seconds: float = 5.0,
    ) -> ManagedProviderState:
        deadline = time.monotonic() + timeout_seconds
        current = self.poll(provider_job_id, model_key=model_key)
        while not current.terminal and time.monotonic() < deadline:
            time.sleep(max(2.0, poll_seconds))
            current = self.poll(provider_job_id, model_key=model_key)
        if not current.terminal:
            raise ManagedProviderError(
                "fal_generation_timeout",
                "fal generation did not complete before the approved timeout.",
                retryable=True,
            )
        return current

    def cancel(self, provider_job_id: str, *, model_key: str) -> None:
        endpoint = self._model_key(model_key)
        self._json_request(
            "PUT",
            f"{self.queue_base_url}/{endpoint}/requests/{provider_job_id}/cancel",
            headers=self.headers,
        )

    @staticmethod
    def _model_key(value: str) -> str:
        normalized = (value or FalQueueRendererAdapter.default_model_key).strip().strip("/")
        if not normalized.startswith("fal-ai/") or ".." in normalized or "://" in normalized:
            raise ManagedProviderError(
                "fal_model_key_invalid",
                "The fal catalogue model key is not an approved fal-ai endpoint.",
            )
        return normalized
