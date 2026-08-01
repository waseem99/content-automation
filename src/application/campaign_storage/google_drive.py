from __future__ import annotations

import hashlib
import http.client
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


class GoogleDriveError(RuntimeError):
    pass


class GoogleDriveNotConfigured(GoogleDriveError):
    pass


@dataclass(frozen=True, slots=True)
class GoogleDriveFile:
    file_id: str
    name: str
    size_bytes: int
    sha256: str
    mime_type: str | None
    parent_folder_id: str | None
    metadata: dict[str, Any]


class GoogleDriveStorage:
    """Official Google Drive v3 adapter using OAuth access tokens from the environment.

    Tokens are never persisted in PostgreSQL or returned from this class. Canonical
    SHA-256 is stored in Drive appProperties because Drive exposes MD5 rather than
    SHA-256 for ordinary files. Strict reconciliation can download and hash bytes.
    """

    api_host = "www.googleapis.com"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        root_folder_id: str | None = None,
        chunk_bytes: int | None = None,
    ) -> None:
        self.access_token = (access_token or os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN") or "").strip()
        self.root_folder_id = (root_folder_id or os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID") or "").strip() or None
        self.chunk_bytes = int(chunk_bytes or os.getenv("GOOGLE_DRIVE_UPLOAD_CHUNK_BYTES", "8388608"))
        if self.chunk_bytes < 256 * 1024:
            raise ValueError("Google Drive upload chunks must be at least 256 KiB")

    @property
    def configured(self) -> bool:
        return bool(self.access_token)

    def require_configured(self) -> None:
        if not self.configured:
            raise GoogleDriveNotConfigured("GOOGLE_DRIVE_ACCESS_TOKEN is not configured")

    def upload_file(
        self,
        source: Path,
        *,
        asset_id: str,
        sha256: str,
        mime_type: str | None,
        parent_folder_id: str | None = None,
        filename: str | None = None,
    ) -> GoogleDriveFile:
        self.require_configured()
        source = source.expanduser().resolve(strict=True)
        if not source.is_file():
            raise GoogleDriveError(f"Google Drive upload source is not a file: {source}")
        size_bytes = source.stat().st_size
        selected_parent = parent_folder_id or self.root_folder_id
        name = filename or source.name
        metadata: dict[str, Any] = {
            "name": name,
            "appProperties": {
                "canonical_asset_id": asset_id,
                "canonical_sha256": sha256,
                "content_automation": "true",
            },
        }
        if selected_parent:
            metadata["parents"] = [selected_parent]
        query = urlencode(
            {
                "uploadType": "resumable",
                "fields": "id,name,size,mimeType,parents,appProperties,md5Checksum,modifiedTime",
            }
        )
        request = Request(
            f"https://{self.api_host}/upload/drive/v3/files?{query}",
            method="POST",
            data=json.dumps(metadata).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime_type or "application/octet-stream",
                "X-Upload-Content-Length": str(size_bytes),
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                session_url = response.headers.get("Location")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise GoogleDriveError(f"Could not create Google Drive resumable session: {exc}") from exc
        if not session_url:
            raise GoogleDriveError("Google Drive did not return a resumable upload URL")
        payload = self._stream_upload(
            session_url,
            source=source,
            size_bytes=size_bytes,
            mime_type=mime_type or "application/octet-stream",
        )
        result = self._file_from_payload(payload, expected_sha256=sha256)
        if result.size_bytes != size_bytes:
            raise GoogleDriveError(
                f"Google Drive size mismatch after upload: expected {size_bytes}, observed {result.size_bytes}"
            )
        return result

    def metadata(self, file_id: str, *, expected_sha256: str | None = None) -> GoogleDriveFile:
        self.require_configured()
        fields = "id,name,size,mimeType,parents,appProperties,md5Checksum,modifiedTime,trashed"
        request = Request(
            f"https://{self.api_host}/drive/v3/files/{quote(file_id, safe='')}?{urlencode({'fields': fields, 'supportsAllDrives': 'true'})}",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(file_id) from exc
            raise GoogleDriveError(f"Google Drive metadata request failed: {exc}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise GoogleDriveError(f"Google Drive metadata request failed: {exc}") from exc
        if payload.get("trashed"):
            raise FileNotFoundError(file_id)
        return self._file_from_payload(payload, expected_sha256=expected_sha256)

    def download_sha256(self, file_id: str) -> tuple[str, int]:
        self.require_configured()
        request = Request(
            f"https://{self.api_host}/drive/v3/files/{quote(file_id, safe='')}?alt=media&supportsAllDrives=true",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        digest = hashlib.sha256()
        size = 0
        try:
            with urlopen(request, timeout=300) as response:
                while True:
                    chunk = response.read(self.chunk_bytes)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
        except HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(file_id) from exc
            raise GoogleDriveError(f"Google Drive download failed: {exc}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise GoogleDriveError(f"Google Drive download failed: {exc}") from exc
        return digest.hexdigest(), size

    def _stream_upload(
        self,
        session_url: str,
        *,
        source: Path,
        size_bytes: int,
        mime_type: str,
    ) -> dict[str, Any]:
        parsed = urlparse(session_url)
        if parsed.scheme != "https" or parsed.hostname != self.api_host:
            raise GoogleDriveError("Unexpected Google Drive resumable upload host")
        connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=600)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        try:
            connection.putrequest("PUT", path)
            connection.putheader("Authorization", f"Bearer {self.access_token}")
            connection.putheader("Content-Type", mime_type)
            connection.putheader("Content-Length", str(size_bytes))
            connection.endheaders()
            with source.open("rb") as stream:
                self._send_stream(connection, stream)
            response = connection.getresponse()
            body = response.read()
            if response.status not in {200, 201}:
                raise GoogleDriveError(
                    f"Google Drive upload failed with HTTP {response.status}: {body[:1000].decode('utf-8', errors='replace')}"
                )
            try:
                return json.loads(body.decode("utf-8"))
            except ValueError as exc:
                raise GoogleDriveError("Google Drive upload returned invalid JSON") from exc
        finally:
            connection.close()

    def _send_stream(self, connection: http.client.HTTPSConnection, stream: BinaryIO) -> None:
        while True:
            chunk = stream.read(self.chunk_bytes)
            if not chunk:
                return
            connection.send(chunk)

    @staticmethod
    def _file_from_payload(payload: dict[str, Any], *, expected_sha256: str | None) -> GoogleDriveFile:
        properties = dict(payload.get("appProperties") or {})
        sha256 = str(properties.get("canonical_sha256") or "")
        if expected_sha256 and sha256 != expected_sha256:
            raise GoogleDriveError(
                f"Google Drive canonical SHA metadata mismatch: expected {expected_sha256}, observed {sha256 or 'missing'}"
            )
        parents = list(payload.get("parents") or [])
        return GoogleDriveFile(
            file_id=str(payload["id"]),
            name=str(payload.get("name") or "file"),
            size_bytes=int(payload.get("size") or 0),
            sha256=sha256,
            mime_type=payload.get("mimeType"),
            parent_folder_id=str(parents[0]) if parents else None,
            metadata={
                "md5_checksum": payload.get("md5Checksum"),
                "modified_time": payload.get("modifiedTime"),
                "app_properties": properties,
            },
        )


__all__ = [
    "GoogleDriveError",
    "GoogleDriveFile",
    "GoogleDriveNotConfigured",
    "GoogleDriveStorage",
]
