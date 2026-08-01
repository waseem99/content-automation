from __future__ import annotations

import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.application.campaign_storage.google_drive import GoogleDriveError, GoogleDriveStorage


def _download_file(self: GoogleDriveStorage, file_id: str, destination: Path) -> Path:
    """Download one Drive object to a private temporary file and atomically publish it.

    OAuth credentials remain environment-only. The caller performs canonical
    SHA-256 and size verification before registering the recovered location.
    """

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.partial")
    url = (
        f"https://{self.api_host}/drive/v3/files/{quote(file_id, safe='')}?"
        "alt=media&supportsAllDrives=true"
    )
    try:
        for attempt in range(2):
            request = Request(
                url,
                headers={"Authorization": f"Bearer {self._token(force_refresh=attempt == 1)}"},
            )
            try:
                with urlopen(request, timeout=300) as response, temporary.open("wb") as stream:
                    while True:
                        chunk = response.read(self.chunk_bytes)
                        if not chunk:
                            break
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
                return destination
            except HTTPError as exc:
                if exc.code == 404:
                    raise FileNotFoundError(file_id) from exc
                if exc.code == 401 and self.renewable and attempt == 0:
                    continue
                raise GoogleDriveError(f"Google Drive recovery download failed: {exc}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                raise GoogleDriveError(f"Google Drive recovery download failed: {exc}") from exc
        raise GoogleDriveError("Google Drive recovery authorization failed after token refresh")
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def install_google_drive_download_patch() -> None:
    if getattr(GoogleDriveStorage, "_p129_download_installed", False):
        return
    GoogleDriveStorage.download_file = _download_file
    GoogleDriveStorage._p129_download_installed = True


__all__ = ["install_google_drive_download_patch"]
