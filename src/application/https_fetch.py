from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urljoin, urlparse

import httpx


UrlValidator = Callable[[str], object]
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class HttpsFetchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HttpsFetchResult:
    final_url: str
    status_code: int
    headers: dict[str, str]
    content: bytes


def _validated_https_url(value: str, *, allowed_hosts: set[str] | None = None) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise HttpsFetchError("only HTTPS URLs are permitted")
    if parsed.username or parsed.password:
        raise HttpsFetchError("URL credentials are not permitted")
    host = parsed.hostname.lower().rstrip(".")
    if allowed_hosts is not None and host not in {item.lower().rstrip(".") for item in allowed_hosts}:
        raise HttpsFetchError(f"HTTPS host is not permitted: {host}")
    return normalized


def fetch_https(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 15,
    max_bytes: int = 512_000,
    max_redirects: int = 5,
    allowed_hosts: set[str] | None = None,
    validator: UrlValidator | None = None,
    transport: httpx.BaseTransport | None = None,
) -> HttpsFetchResult:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if max_redirects < 0:
        raise ValueError("max_redirects cannot be negative")

    current = url
    try:
        with httpx.Client(
            follow_redirects=False,
            trust_env=False,
            timeout=timeout,
            transport=transport,
        ) as client:
            for redirect_count in range(max_redirects + 1):
                current = _validated_https_url(current, allowed_hosts=allowed_hosts)
                if validator is not None:
                    validator(current)

                with client.stream("GET", current, headers=headers) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        if redirect_count >= max_redirects:
                            raise HttpsFetchError("HTTPS redirect limit exceeded")
                        location = response.headers.get("location")
                        if not location:
                            raise HttpsFetchError("HTTPS redirect omitted Location")
                        current = urljoin(current, location)
                        continue

                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        remaining = max_bytes - len(body)
                        if remaining <= 0:
                            break
                        body.extend(chunk[:remaining])
                        if len(body) >= max_bytes:
                            break
                    return HttpsFetchResult(
                        final_url=str(response.url),
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        content=bytes(body),
                    )
    except HttpsFetchError:
        raise
    except httpx.HTTPError as exc:
        raise HttpsFetchError(f"HTTPS request failed: {exc}") from exc

    raise HttpsFetchError("HTTPS request did not complete")


__all__ = ["HttpsFetchError", "HttpsFetchResult", "fetch_https"]
