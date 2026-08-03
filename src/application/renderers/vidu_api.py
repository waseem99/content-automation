from __future__ import annotations

import json
import os
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from src.application.renderers.provider_http import (
    ManagedHttpAdapter,
    ManagedProviderError,
    ManagedProviderState,
)


class ViduRendererAdapter(ManagedHttpAdapter):
    """Official Vidu Enterprise v2 image-to-video adapter."""

    provider_key = "vidu"
    default_model_key = "viduq3-pro-fast"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self.api_key = (api_key or os.getenv("VIDU_API_KEY", "")).strip()
        if not self.api_key:
            raise ManagedProviderError(
                "vidu_api_key_missing",
                "VIDU_API_KEY is required in the worker environment.",
            )
        self.base_url = (base_url or os.getenv("VIDU_API_BASE_URL", "https://api.vidu.com")).rstrip("/")
        if not self.base_url.startswith("https://"):
            raise ManagedProviderError(
                "vidu_base_url_invalid",
                "The Vidu API base URL must use HTTPS.",
            )
        raw_credit_price = os.getenv("VIDU_USD_PER_CREDIT", "").strip()
        try:
            self.usd_per_credit = Decimal(raw_credit_price) if raw_credit_price else None
        except InvalidOperation as exc:
            raise ManagedProviderError(
                "vidu_credit_price_invalid",
                "VIDU_USD_PER_CREDIT must be a valid non-negative decimal.",
            ) from exc
        if self.usd_per_credit is not None and self.usd_per_credit < 0:
            raise ManagedProviderError(
                "vidu_credit_price_invalid",
                "VIDU_USD_PER_CREDIT must be non-negative.",
            )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit(
        self,
        *,
        model_key: str,
        request_payload: Mapping[str, Any],
        input_paths: list[Path],
    ) -> ManagedProviderState:
        if len(input_paths) != 1:
            raise ManagedProviderError(
                "vidu_single_image_required",
                "Vidu image-to-video requires exactly one reviewed input image.",
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
                "vidu_prompt_missing",
                "The managed route has no reviewed Vidu prompt.",
            )
        duration = max(1, min(16, int(round(float(request_payload.get("duration_seconds") or 5)))))
        model = (model_key or self.default_model_key).strip()
        if not model or len(model) > 200 or "://" in model:
            raise ManagedProviderError(
                "vidu_model_key_invalid",
                "The Vidu catalogue model key is invalid.",
            )
        transparent_payload = {
            "generation_job_id": metadata.get("generation_job_id"),
            "routing_item_id": metadata.get("routing_item_id"),
            "request_fingerprint": metadata.get("request_fingerprint"),
        }
        body: dict[str, Any] = {
            "model": model,
            "images": [self.data_uri(input_paths[0])],
            "prompt": prompt,
            "duration": duration,
            "resolution": str(metadata.get("resolution") or "720p"),
            "movement_amplitude": str(metadata.get("movement_amplitude") or "auto"),
            "off_peak": bool(metadata.get("off_peak", False)),
            "audio": bool(metadata.get("audio", False)),
            "payload": json.dumps(transparent_payload, sort_keys=True, separators=(",", ":")),
        }
        if metadata.get("seed") is not None:
            body["seed"] = int(metadata["seed"])
        response = self._json_request(
            "POST",
            f"{self.base_url}/ent/v2/img2video",
            headers=self.headers,
            payload=body,
            timeout=max(self.timeout_seconds, 180),
        )
        task_id = self._first_text(response, ("task_id", "taskId", "id"))
        if not task_id:
            raise ManagedProviderError(
                "vidu_task_id_missing",
                "Vidu accepted the request without returning a task ID.",
                retryable=True,
            )
        return self._state(task_id, response)

    def poll(self, provider_job_id: str, *, model_key: str) -> ManagedProviderState:
        del model_key
        response = self._json_request(
            "GET",
            f"{self.base_url}/ent/v2/tasks/{provider_job_id}/creations",
            headers=self.headers,
        )
        return self._state(provider_job_id, response)

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
                "vidu_generation_timeout",
                "Vidu generation did not complete before the approved timeout.",
                retryable=True,
            )
        return current

    def _state(self, task_id: str, payload: dict[str, Any]) -> ManagedProviderState:
        raw = (self._first_text(payload, ("state", "status")) or "created").strip().lower()
        if raw in {"success", "succeeded", "completed", "complete", "done"}:
            status = "succeeded"
        elif raw in {"failed", "error", "rejected"}:
            status = "failed"
        elif raw in {"cancelled", "canceled"}:
            status = "cancelled"
        else:
            status = "running"
        credits = self._decimal(payload, ("credits", "credit", "points"))
        observed = self._decimal(
            payload,
            ("actual_cost_usd", "cost_usd", "usd_cost", "total_cost_usd"),
        )
        if observed is None and credits is not None and self.usd_per_credit is not None:
            observed = credits * self.usd_per_credit
        output_url = self._first_url(payload) if status == "succeeded" else None
        if status == "succeeded" and not output_url:
            raise ManagedProviderError(
                "vidu_output_url_missing",
                "Vidu completed the task without a downloadable creation URL.",
                retryable=True,
                actual_cost_usd=observed or Decimal("0"),
            )
        return ManagedProviderState(
            provider_job_id=task_id,
            status=status,
            payload=payload,
            output_url=output_url,
            actual_cost_usd=observed,
            credits=credits,
            error=(self._first_text(payload, ("error", "message", "detail")) if status == "failed" else None),
        )
