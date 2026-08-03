from __future__ import annotations

from urllib.request import Request

from src.application.campaign_storage import google_drive as _google_drive
from src.application.campaign_storage.secure_https import open_allowlisted_https


_GOOGLE_HTTPS_HOSTS = frozenset(
    {
        "www.googleapis.com",
        "oauth2.googleapis.com",
    }
)


def _secure_google_urlopen(request: Request, timeout: int):
    return open_allowlisted_https(
        request,
        timeout=timeout,
        allowed_hosts=_GOOGLE_HTTPS_HOSTS,
    )


def install_google_drive_transport_patch() -> None:
    if getattr(_google_drive, "_p135_secure_transport_installed", False):
        return
    _google_drive.urlopen = _secure_google_urlopen
    _google_drive._p135_secure_transport_installed = True


__all__ = ["install_google_drive_transport_patch"]
