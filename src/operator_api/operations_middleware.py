from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import defaultdict, deque
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.operations.settings import OperationsSettings


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_LOGGER = logging.getLogger("content_automation.operations")


@dataclass(slots=True)
class _RateWindow:
    timestamps: deque[float]


@dataclass(frozen=True, slots=True)
class _RateIdentity:
    key: str
    scope: str
    requests_per_minute: int


class OperationsSafetyMiddleware:
    """ASGI request ID, streaming body limit, bounded rate limit, and safe error boundary."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: OperationsSettings,
        trusted_operator_keys: Collection[str] | None = None,
    ) -> None:
        self.app = app
        self.settings = settings
        # Retain only one-way hashes. Unknown or forged operator keys never earn
        # a separate or larger rate window and remain in the client bucket.
        self._trusted_operator_key_hashes = frozenset(
            hashlib.sha256(key.encode("utf-8")).hexdigest()
            for key in (trusted_operator_keys or ())
            if key
        )
        self._rate_windows: dict[str, _RateWindow] = defaultdict(lambda: _RateWindow(deque()))
        self._rate_lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        request_id = self._request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        path = str(scope.get("path") or "/")
        method = str(scope.get("method") or "GET")
        rate_identity = self._rate_identity(scope)

        if not self._rate_limit_exempt(path):
            allowed, retry_after = await self._allow_request(
                rate_identity.key,
                requests_per_minute=rate_identity.requests_per_minute,
            )
            if not allowed:
                await self._json_response(
                    send,
                    status=429,
                    payload={
                        "detail": "rate_limit_exceeded",
                        "request_id": request_id,
                        "rate_limit_scope": rate_identity.scope,
                    },
                    request_id=request_id,
                    extra_headers=[(b"retry-after", str(retry_after).encode("ascii"))],
                )
                self._log(
                    request_id=request_id,
                    method=method,
                    path=path,
                    status=429,
                    duration_ms=(time.monotonic() - started) * 1000,
                    client_hash=rate_identity.key,
                    rate_limit_scope=rate_identity.scope,
                )
                return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self.settings.max_request_body_bytes:
            await self._json_response(
                send,
                status=413,
                payload={
                    "detail": "request_body_too_large",
                    "request_id": request_id,
                },
                request_id=request_id,
            )
            self._log(
                request_id=request_id,
                method=method,
                path=path,
                status=413,
                duration_ms=(time.monotonic() - started) * 1000,
                client_hash=rate_identity.key,
                rate_limit_scope=rate_identity.scope,
            )
            return

        received_bytes = 0
        response_status = 500

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.settings.max_request_body_bytes:
                    raise _BodyLimitExceeded
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _BodyLimitExceeded:
            response_status = 413
            await self._json_response(
                send,
                status=413,
                payload={
                    "detail": "request_body_too_large",
                    "request_id": request_id,
                },
                request_id=request_id,
            )
        except Exception:
            response_status = 500
            _LOGGER.exception(
                json.dumps(
                    {
                        "event": "unhandled_request_error",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "client_hash": rate_identity.key,
                        "rate_limit_scope": rate_identity.scope,
                    },
                    sort_keys=True,
                )
            )
            await self._json_response(
                send,
                status=500,
                payload={
                    "detail": "internal_server_error",
                    "request_id": request_id,
                },
                request_id=request_id,
            )
        finally:
            self._log(
                request_id=request_id,
                method=method,
                path=path,
                status=response_status,
                duration_ms=(time.monotonic() - started) * 1000,
                client_hash=rate_identity.key,
                rate_limit_scope=rate_identity.scope,
                request_bytes=received_bytes,
            )

    def _rate_limit_exempt(self, path: str) -> bool:
        if path in self.settings.rate_limit_exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.settings.rate_limit_exempt_prefixes)

    async def _allow_request(
        self,
        rate_key: str,
        *,
        requests_per_minute: int,
    ) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - 60
        async with self._rate_lock:
            window = self._rate_windows[rate_key].timestamps
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= requests_per_minute:
                retry_after = max(int(60 - (now - window[0])) + 1, 1)
                return False, retry_after
            window.append(now)
            if len(self._rate_windows) > 10_000:
                stale = [key for key, item in self._rate_windows.items() if not item.timestamps or item.timestamps[-1] <= cutoff]
                for key in stale[:1000]:
                    self._rate_windows.pop(key, None)
            return True, 0

    def _rate_identity(self, scope: Scope) -> _RateIdentity:
        client = scope.get("client")
        host = str(client[0]) if client else "unknown"
        client_key = hashlib.sha256(f"client:{host}".encode("utf-8")).hexdigest()[:16]

        operator_key = self._header(scope, b"x-operator-key")
        if operator_key:
            operator_digest = hashlib.sha256(operator_key).hexdigest()
            if operator_digest in self._trusted_operator_key_hashes:
                bounded_key = hashlib.sha256(b"operator:" + operator_key).hexdigest()[:16]
                return _RateIdentity(
                    key=bounded_key,
                    scope="authenticated_operator",
                    requests_per_minute=self.settings.authenticated_requests_per_minute,
                )

        return _RateIdentity(
            key=client_key,
            scope="client",
            requests_per_minute=self.settings.requests_per_minute,
        )

    @staticmethod
    def _header(scope: Scope, expected_name: bytes) -> bytes:
        for name, value in scope.get("headers", []):
            if name.lower() == expected_name:
                return bytes(value)
        return b""

    @staticmethod
    def _request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                candidate = value.decode("ascii", errors="ignore")
                if _REQUEST_ID_PATTERN.fullmatch(candidate):
                    return candidate
                break
        return f"req-{uuid4()}"

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    parsed = int(value)
                except ValueError:
                    return None
                return max(parsed, 0)
        return None

    @staticmethod
    async def _json_response(
        send: Send,
        *,
        status: int,
        payload: dict[str, Any],
        request_id: str,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-request-id", request_id.encode("ascii")),
            (b"cache-control", b"no-store"),
            *(extra_headers or []),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    def _log(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        client_hash: str,
        rate_limit_scope: str,
        request_bytes: int = 0,
    ) -> None:
        if not self.settings.structured_logs:
            return
        _LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "service": self.settings.service_name,
                    "environment": self.settings.environment,
                    "release_key": self.settings.release_key,
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": status,
                    "duration_ms": round(duration_ms, 3),
                    "request_bytes": request_bytes,
                    "client_hash": client_hash,
                    "rate_limit_scope": rate_limit_scope,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


class _BodyLimitExceeded(Exception):
    pass
