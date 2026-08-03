from __future__ import annotations

from collections.abc import Collection
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SecureHttpsError(ValueError):
    pass


def _validate_https_url(url: str, *, allowed_hosts: Collection[str]) -> None:
    parsed = urlparse(url)
    normalized_hosts = {host.strip().lower() for host in allowed_hosts if host.strip()}
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise SecureHttpsError("Only HTTPS transport is permitted")
    if not hostname or hostname not in normalized_hosts:
        raise SecureHttpsError("HTTPS destination is not in the transport allowlist")
    if parsed.username is not None or parsed.password is not None:
        raise SecureHttpsError("Embedded URL credentials are not permitted")
    if parsed.port not in {None, 443}:
        raise SecureHttpsError("Only the standard HTTPS port is permitted")


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: Collection[str]) -> None:
        super().__init__()
        self.allowed_hosts = frozenset(allowed_hosts)

    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> Request | None:
        _validate_https_url(newurl, allowed_hosts=self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_allowlisted_https(
    request: Request,
    *,
    timeout: int,
    allowed_hosts: Collection[str],
):
    """Open one HTTPS request and reject cross-scheme or cross-host redirects."""

    _validate_https_url(request.full_url, allowed_hosts=allowed_hosts)
    opener = build_opener(_AllowlistedRedirectHandler(allowed_hosts))
    return opener.open(request, timeout=timeout)


__all__ = ["SecureHttpsError", "open_allowlisted_https"]
