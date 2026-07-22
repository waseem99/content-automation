from __future__ import annotations

from urllib.parse import urlsplit


class LocalEndpointError(ValueError):
    pass


_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def validate_local_http_endpoint(endpoint: str) -> str:
    normalized = endpoint.strip().rstrip("/")
    try:
        parsed = urlsplit(normalized)
    except ValueError as exc:
        raise LocalEndpointError("local model endpoint is invalid; use a localhost loopback origin") from exc
    if parsed.scheme.lower() != "http":
        raise LocalEndpointError("local model endpoint must use plain HTTP on localhost or loopback")
    if parsed.hostname is None or parsed.hostname.lower() not in _ALLOWED_HOSTS:
        raise LocalEndpointError("local model endpoint must resolve to localhost or loopback")
    if parsed.username is not None or parsed.password is not None:
        raise LocalEndpointError("local model endpoint cannot include credentials; use a localhost origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LocalEndpointError("local model endpoint must contain only a localhost loopback origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LocalEndpointError("local model endpoint localhost port is invalid") from exc
    if port is not None and not 1 <= port <= 65535:
        raise LocalEndpointError("local model endpoint localhost port is invalid")
    return normalized
