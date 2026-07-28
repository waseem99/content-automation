from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HiggsfieldCliError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class HiggsfieldJobState:
    provider_job_id: str
    status: str
    payload: dict[str, Any]
    output_url: str | None = None
    actual_cost_usd: Decimal | None = None
    error: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}


class HiggsfieldCliRendererAdapter:
    """Official Higgsfield CLI adapter; never uses browser sessions or private APIs."""

    provider_key = "higgsfield"

    def __init__(self, *, executable: str | None = None, timeout_seconds: int = 120) -> None:
        configured = executable or os.getenv("HIGGSFIELD_CLI_PATH", "higgsfield")
        resolved = shutil.which(configured) if not Path(configured).is_file() else configured
        if not resolved:
            raise HiggsfieldCliError(
                "higgsfield_cli_unavailable",
                "The official Higgsfield CLI is not installed or visible on PATH.",
            )
        self.executable = str(resolved)
        self.timeout_seconds = timeout_seconds

    def health(self, *, model_key: str) -> dict[str, Any]:
        payload = self._run_json(
            ["model", "get", model_key, "--json", "--no-color"],
            operation="model_get",
            timeout=min(self.timeout_seconds, 60),
        )
        return {
            "ok": True,
            "provider": self.provider_key,
            "model_key": model_key,
            "model": payload,
        }

    def submit(
        self,
        *,
        model_key: str,
        request_payload: Mapping[str, Any],
        input_paths: Iterable[Path],
    ) -> HiggsfieldJobState:
        paths = [path.resolve(strict=True) for path in input_paths]
        metadata = dict(request_payload.get("request_metadata") or {})
        args = self._generation_arguments(
            request_payload=request_payload,
            metadata=metadata,
            input_paths=paths,
        )
        payload = self._run_json(
            ["generate", "create", model_key, *args, "--json", "--no-color"],
            operation="generate_create",
            timeout=max(self.timeout_seconds, 180),
        )
        provider_job_id = self._first_text(
            payload,
            ("generation_id", "job_id", "request_id", "id"),
        )
        if not provider_job_id:
            raise HiggsfieldCliError(
                "higgsfield_job_id_missing",
                "Higgsfield accepted the request without returning a generation ID.",
                retryable=True,
            )
        return self._state(provider_job_id, payload)

    def poll(self, provider_job_id: str) -> HiggsfieldJobState:
        payload = self._run_json(
            ["generate", "get", provider_job_id, "--json", "--no-color"],
            operation="generate_get",
            timeout=self.timeout_seconds,
        )
        return self._state(provider_job_id, payload)

    def wait(
        self,
        provider_job_id: str,
        *,
        timeout_seconds: int,
        poll_seconds: float = 5.0,
    ) -> HiggsfieldJobState:
        deadline = time.monotonic() + timeout_seconds
        current = self.poll(provider_job_id)
        while not current.terminal and time.monotonic() < deadline:
            time.sleep(max(2.0, poll_seconds))
            current = self.poll(provider_job_id)
        if not current.terminal:
            raise HiggsfieldCliError(
                "higgsfield_generation_timeout",
                "Higgsfield generation did not complete before the approved timeout.",
                retryable=True,
            )
        return current

    def download(self, state: HiggsfieldJobState, destination: Path) -> Path:
        if state.status != "succeeded" or not state.output_url:
            raise HiggsfieldCliError(
                "higgsfield_output_unavailable",
                "The Higgsfield generation has no completed downloadable output.",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(state.output_url, method="GET", headers={"User-Agent": "ContentAutomation/1.0"})
        try:
            # The provider URL is accepted only from the official CLI job response and must be HTTPS.
            with urlopen(request, timeout=max(self.timeout_seconds, 300)) as response:  # nosec B310
                with destination.open("wb") as handle:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
        except HTTPError as exc:
            raise HiggsfieldCliError(
                f"higgsfield_download_http_{exc.code}",
                "The completed Higgsfield output could not be downloaded.",
                retryable=exc.code in {408, 429, 500, 502, 503, 504},
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise HiggsfieldCliError(
                "higgsfield_download_unavailable",
                "The completed Higgsfield output could not be downloaded.",
                retryable=True,
            ) from exc
        if not destination.is_file() or destination.stat().st_size == 0:
            raise HiggsfieldCliError(
                "higgsfield_download_empty",
                "The downloaded Higgsfield output is empty.",
                retryable=True,
            )
        return destination

    def _generation_arguments(
        self,
        *,
        request_payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
        input_paths: list[Path],
    ) -> list[str]:
        explicit = metadata.get("higgsfield_cli_arguments")
        if explicit is not None:
            if not isinstance(explicit, list) or not all(isinstance(value, str) for value in explicit):
                raise HiggsfieldCliError(
                    "higgsfield_cli_arguments_invalid",
                    "Reviewed Higgsfield CLI arguments must be a list of strings.",
                )
            replacements = {
                f"{{input_asset_{index}}}": str(path)
                for index, path in enumerate(input_paths)
            }
            arguments: list[str] = []
            for raw in explicit:
                value = raw
                for placeholder, path in replacements.items():
                    value = value.replace(placeholder, path)
                arguments.append(value)
            self._validate_arguments(arguments)
            return arguments

        prompt = str(metadata.get("prompt") or metadata.get("approved_prompt") or "").strip()
        if not prompt:
            raise HiggsfieldCliError(
                "higgsfield_prompt_missing",
                "The managed route has no reviewed Higgsfield prompt.",
            )
        arguments = ["--prompt", prompt]
        if input_paths:
            arguments.extend(["--start-image", str(input_paths[0])])
        duration = str(request_payload.get("duration_seconds") or "").strip()
        if duration:
            arguments.extend(["--duration", duration])
        width = int(request_payload.get("width") or 0)
        height = int(request_payload.get("height") or 0)
        if width > 0 and height > 0:
            arguments.extend(["--aspect-ratio", self._aspect_ratio(width, height)])
        self._validate_arguments(arguments)
        return arguments

    @staticmethod
    def _validate_arguments(arguments: list[str]) -> None:
        forbidden = {
            "--token",
            "--api-key",
            "--api_key",
            "--password",
            "--cookie",
            "--cookies",
            "--auth-header",
        }
        for value in arguments:
            lowered = value.strip().lower()
            if lowered in forbidden or any(lowered.startswith(f"{flag}=") for flag in forbidden):
                raise HiggsfieldCliError(
                    "higgsfield_secret_argument_forbidden",
                    "Credentials cannot be supplied through generation arguments.",
                )
        if "--json" in arguments or "--no-color" in arguments:
            raise HiggsfieldCliError(
                "higgsfield_global_argument_reserved",
                "JSON and color controls are managed by the worker.",
            )

    def _state(self, provider_job_id: str, payload: dict[str, Any]) -> HiggsfieldJobState:
        raw_status = (
            self._first_text(payload, ("status", "state", "generation_status"))
            or "unknown"
        ).strip().lower().replace("-", "_")
        if raw_status in {"success", "succeeded", "completed", "complete", "ready", "done"}:
            status = "succeeded"
        elif raw_status in {"failed", "error", "rejected"}:
            status = "failed"
        elif raw_status in {"cancelled", "canceled"}:
            status = "cancelled"
        else:
            status = "running"
        output_url = self._first_url(payload)
        cost = self._cost(payload)
        error = self._first_text(payload, ("error", "error_message", "message")) if status == "failed" else None
        return HiggsfieldJobState(
            provider_job_id=provider_job_id,
            status=status,
            payload=payload,
            output_url=output_url,
            actual_cost_usd=cost,
            error=error,
        )

    def _run_json(
        self,
        arguments: list[str],
        *,
        operation: str,
        timeout: int,
    ) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                [self.executable, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            raise HiggsfieldCliError(
                f"higgsfield_{operation}_timeout",
                f"The official Higgsfield CLI timed out during {operation}.",
                retryable=True,
            ) from exc
        except OSError as exc:
            raise HiggsfieldCliError(
                f"higgsfield_{operation}_unavailable",
                f"The official Higgsfield CLI could not run {operation}.",
                retryable=True,
            ) from exc
        if completed.returncode != 0:
            message = self._redacted_error(completed.stderr or completed.stdout)
            retryable = any(
                marker in message.lower()
                for marker in ("timeout", "rate limit", "temporarily", "unavailable", "try again")
            )
            raise HiggsfieldCliError(
                f"higgsfield_{operation}_failed",
                message or f"The official Higgsfield CLI failed during {operation}.",
                retryable=retryable,
            )
        raw = completed.stdout.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HiggsfieldCliError(
                f"higgsfield_{operation}_invalid_json",
                "The official Higgsfield CLI did not return valid JSON.",
                retryable=True,
            ) from exc
        if not isinstance(payload, dict):
            payload = {"result": payload}
        return payload

    @staticmethod
    def _redacted_error(value: str) -> str:
        cleaned = " ".join(value.split())[:2000]
        for marker in ("token", "authorization", "cookie", "secret"):
            if marker in cleaned.lower():
                return "The official Higgsfield CLI returned a redacted authentication or provider error."
        return cleaned

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
            for key in ("download_url", "output_url", "video_url", "url"):
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
    def _cost(cls, payload: Any) -> Decimal | None:
        if isinstance(payload, Mapping):
            for key in ("actual_cost_usd", "cost_usd", "usd_cost", "total_cost_usd"):
                value = payload.get(key)
                if value is not None:
                    try:
                        return Decimal(str(value))
                    except InvalidOperation:
                        pass
            for value in payload.values():
                found = cls._cost(value)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload:
                found = cls._cost(value)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> str:
        from math import gcd

        divisor = gcd(width, height)
        return f"{width // divisor}:{height // divisor}"
