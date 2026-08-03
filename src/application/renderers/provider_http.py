from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx


class ManagedProviderError(RuntimeError):
    """Safe provider failure carrying retry and incurred-cost evidence."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        actual_cost_usd: Decimal = Decimal("0"),
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.actual_cost_usd = max(Decimal("0"), actual_cost_usd)
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ManagedProviderState:
    provider_job_id: str
    status: str
    payload: dict[str, Any]
    output_url: str | None = None
    actual_cost_usd: Decimal | None = None
    credits: Decimal | None = None
    error: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}


class ManagedHttpAdapter:
    """Shared safe HTTP behavior for official managed-render APIs."""

    provider_key: str

    def __init__(self, *, timeout_seconds: int = 120) -> None:
        self.timeout_seconds = timeout_seconds
        self.client = httpx.Client(
            timeout=httpx.Timeout(float(timeout_seconds), connect=30.0),
            follow_redirects=True,
            headers={"User-Agent": "ContentAutomation/1.0"},
        )

    def close(self) -> None:
        self.client.close()

    def download(self, state: ManagedProviderState, destination: Path) -> Path:
        if state.status != "succeeded" or not state.output_url:
            raise ManagedProviderError(
                f"{self.provider_key}_output_unavailable",
                f"The completed {self.provider_key} request has no downloadable output.",
            )
        parsed = urlparse(state.output_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ManagedProviderError(
                f"{self.provider_key}_output_url_invalid",
                f"The {self.provider_key} output URL is not an HTTPS provider URL.",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.client.stream("GET", state.output_url, timeout=None) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for block in response.iter_bytes(1024 * 1024):
                        if block:
                            handle.write(block)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ManagedProviderError(
                f"{self.provider_key}_download_unavailable",
                f"The completed {self.provider_key} output could not be downloaded.",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ManagedProviderError(
                f"{self.provider_key}_download_http_{exc.response.status_code}",
                f"The completed {self.provider_key} output could not be downloaded.",
                retryable=exc.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504},
            ) from exc
        except OSError as exc:
            raise ManagedProviderError(
                f"{self.provider_key}_download_write_failed",
                f"The completed {self.provider_key} output could not be stored locally.",
                retryable=True,
            ) from exc
        if not destination.is_file() or destination.stat().st_size == 0:
            raise ManagedProviderError(
                f"{self.provider_key}_download_empty",
                f"The downloaded {self.provider_key} output is empty.",
                retryable=True,
            )
        return destination

    def _json_request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.request(
                method,
                url,
                headers=dict(headers),
                json=dict(payload) if payload is not None else None,
                timeout=timeout or self.timeout_seconds,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ManagedProviderError(
                f"{self.provider_key}_request_unavailable",
                f"The official {self.provider_key} API is temporarily unreachable.",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            message = self._safe_error_message(exc.response)
            raise ManagedProviderError(
                f"{self.provider_key}_http_{status}",
                message,
                retryable=status in {408, 409, 425, 429, 500, 502, 503, 504},
                details={"http_status": status},
            ) from exc
        try:
            value = response.json()
        except ValueError as exc:
            raise ManagedProviderError(
                f"{self.provider_key}_invalid_json",
                f"The official {self.provider_key} API returned invalid JSON.",
                retryable=True,
            ) from exc
        return value if isinstance(value, dict) else {"result": value}

    def _safe_error_message(self, response: httpx.Response) -> str:
        generic = f"The official {self.provider_key} API rejected the request."
        try:
            payload = response.json()
        except ValueError:
            return generic
        candidate = self._first_text(payload, ("detail", "message", "error", "error_message"))
        if not candidate:
            return generic
        lowered = candidate.lower()
        if any(marker in lowered for marker in ("token", "api key", "authorization", "cookie", "secret")):
            return f"The official {self.provider_key} API returned a redacted authentication error."
        return candidate[:2000]

    @staticmethod
    def data_uri(path: Path, *, maximum_bytes: int = 19 * 1024 * 1024) -> str:
        source = path.resolve(strict=True)
        size = source.stat().st_size
        if size <= 0 or size > maximum_bytes:
            raise ManagedProviderError(
                "provider_input_size_invalid",
                "The reviewed input image is empty or exceeds the provider-safe upload limit.",
            )
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        if mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise ManagedProviderError(
                "provider_input_format_invalid",
                "Managed image-to-video inputs must be PNG, JPEG, or WebP.",
            )
        encoded = base64.b64encode(source.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    @classmethod
    def _first_text(cls, payload: Any, keys: tuple[str, ...]) -> str | None:
        if isinstance(payload, Mapping):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, (str, int)) and str(value).strip():
                    return str(value)
            for value in payload.values():
                found = cls._first_text(value, keys)
                if found:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = cls._first_text(value, keys)
                if found:
                    return found
        return None

    @classmethod
    def _first_url(cls, payload: Any) -> str | None:
        if isinstance(payload, Mapping):
            preferred = ("download_url", "output_url", "video_url", "uri", "url")
            for key in preferred:
                value = payload.get(key)
                if isinstance(value, str) and value.startswith("https://"):
                    return value
            for value in payload.values():
                found = cls._first_url(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = cls._first_url(value)
                if found:
                    return found
        return None

    @classmethod
    def _decimal(cls, payload: Any, keys: tuple[str, ...]) -> Decimal | None:
        if isinstance(payload, Mapping):
            for key in keys:
                value = payload.get(key)
                if value is not None:
                    try:
                        return Decimal(str(value))
                    except (InvalidOperation, ValueError):
                        pass
            for value in payload.values():
                found = cls._decimal(value, keys)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = cls._decimal(value, keys)
                if found is not None:
                    return found
        return None

    @staticmethod
    def payload_digest(payload: Mapping[str, Any]) -> str:
        import hashlib

        return hashlib.sha256(
            json.dumps(dict(payload), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
