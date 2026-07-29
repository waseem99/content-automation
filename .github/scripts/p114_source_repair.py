from __future__ import annotations

from pathlib import Path


HELPER = '''from __future__ import annotations

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
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new)


def repair_automatic_evidence() -> None:
    path = Path("src/application/scripts/automatic_evidence.py")
    text = path.read_text(encoding="utf-8")
    if "from src.application.https_fetch import HttpsFetchError, fetch_https" in text:
        if "urlopen(" in text:
            raise RuntimeError("automatic_evidence contains mixed old and new HTTPS implementations")
        return

    text = replace_once(text, "from urllib.error import HTTPError, URLError\n", "", "automatic error imports")
    text = replace_once(text, "from urllib.request import Request, urlopen\n", "", "automatic request imports")
    text = replace_once(
        text,
        "from src.infrastructure.database.connection import Database\n",
        "from src.application.https_fetch import HttpsFetchError, fetch_https\nfrom src.infrastructure.database.connection import Database\n",
        "automatic helper import",
    )
    text = replace_once(
        text,
        '''        request = Request(\n            f"{self.endpoint}?{params}",\n            headers={"User-Agent": self.user_agent, "Accept": "application/json"},\n        )\n        with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed Wikipedia endpoint\n            payload = json.loads(response.read(512_000).decode("utf-8"))\n''',
        '''        response = fetch_https(\n            f"{self.endpoint}?{params}",\n            headers={"User-Agent": self.user_agent, "Accept": "application/json"},\n            timeout=12,\n            max_bytes=512_000,\n            allowed_hosts={"en.wikipedia.org"},\n        )\n        payload = json.loads(response.content.decode("utf-8"))\n''',
        "automatic Wikipedia fetch",
    )
    text = replace_once(
        text,
        '''        request = Request(\n            safe_url,\n            headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},\n        )\n        try:\n            with urlopen(request, timeout=12) as response:  # noqa: S310 - strict public HTTPS validation\n                final_url = response.geturl()\n                self._assert_public_https_url(final_url)\n                raw = response.read(512_000)\n        except (HTTPError, URLError, TimeoutError, OSError) as exc:\n            raise RuntimeError(f"source_url_validation_failed: {exc}") from exc\n''',
        '''        try:\n            response = fetch_https(\n                safe_url,\n                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},\n                timeout=12,\n                max_bytes=512_000,\n                validator=self._assert_public_https_url,\n            )\n            final_url = response.final_url\n            raw = response.content\n        except HttpsFetchError as exc:\n            raise RuntimeError(f"source_url_validation_failed: {exc}") from exc\n''',
        "automatic public URL fetch",
    )
    path.write_text(text, encoding="utf-8")


def repair_p110_runtime() -> None:
    path = Path("src/operator_api/p110_runtime.py")
    text = path.read_text(encoding="utf-8")
    if "from src.application.https_fetch import HttpsFetchError, fetch_https" in text:
        if "urlopen(" in text:
            raise RuntimeError("p110_runtime contains mixed old and new HTTPS implementations")
        return

    text = replace_once(text, "from urllib.error import HTTPError, URLError\n", "", "P110 error imports")
    text = replace_once(text, "from urllib.request import Request, urlopen\n", "", "P110 request imports")
    text = replace_once(
        text,
        "from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType\n",
        "from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType\nfrom src.application.https_fetch import HttpsFetchError, fetch_https\n",
        "P110 helper import",
    )
    text = replace_once(
        text,
        '''        request = Request(f"{self.endpoint}?{params}", headers={"User-Agent": self.user_agent, "Accept": "application/json"})\n        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed official HTTPS host\n            payload = json.loads(response.read(512_000).decode("utf-8"))\n''',
        '''        response = fetch_https(\n            f"{self.endpoint}?{params}",\n            headers={"User-Agent": self.user_agent, "Accept": "application/json"},\n            timeout=15,\n            max_bytes=512_000,\n            allowed_hosts={"en.wikipedia.org"},\n        )\n        payload = json.loads(response.content.decode("utf-8"))\n''',
        "P110 Wikipedia fetch",
    )
    text = replace_once(
        text,
        '''    request = Request(\n        safe_url,\n        headers={\n            "User-Agent": "ContentAutomationP110/1.0 (operator-selected source validation)",\n            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.8,*/*;q=0.5",\n        },\n    )\n    try:\n        with urlopen(request, timeout=15) as response:  # noqa: S310 - URL passed strict public HTTPS/SSRF validation\n            final_url = response.geturl()\n            _, final_host = _assert_public_https_url(final_url)\n            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()\n            raw = response.read(512_000)\n    except (HTTPError, URLError, TimeoutError, OSError) as exc:\n        raise P110Error("source_url_validation_failed", details={"message": str(exc)}) from exc\n''',
        '''    try:\n        response = fetch_https(\n            safe_url,\n            headers={\n                "User-Agent": "ContentAutomationP110/1.0 (operator-selected source validation)",\n                "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.8,*/*;q=0.5",\n            },\n            timeout=15,\n            max_bytes=512_000,\n            validator=_assert_public_https_url,\n        )\n        final_url = response.final_url\n        _, final_host = _assert_public_https_url(final_url)\n        content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()\n        raw = response.content\n    except HttpsFetchError as exc:\n        raise P110Error("source_url_validation_failed", details={"message": str(exc)}) from exc\n''',
        "P110 public URL fetch",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    helper = Path("src/application/https_fetch.py")
    helper.write_text(HELPER, encoding="utf-8")
    repair_automatic_evidence()
    repair_p110_runtime()


if __name__ == "__main__":
    main()
