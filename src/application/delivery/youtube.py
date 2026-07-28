from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from src.application.assets.hashing import inspect_file
from src.application.delivery.adapters import DeliveryAdapterError
from src.application.delivery.models import (
    DeliveryAdapterRequest,
    DeliveryAdapterResult,
    DeliveryPrivacy,
)
from src.application.delivery.reconciliation import (
    DeliveryPlatformStatus,
    DeliveryReconciliationResult,
)
from src.application.shared_storage.providers import SharedStorageError
from src.application.shared_storage.runtime import SharedProviderRegistry


class YouTubeOfficialDeliveryAdapter:
    """Official YouTube Data API adapter with private-by-default safety."""

    adapter_key = "youtube-official"
    token_url = "https://oauth2.googleapis.com/token"
    upload_url = (
        "https://www.googleapis.com/upload/youtube/v3/videos?"
        "uploadType=resumable&part=snippet,status"
    )
    video_status_url = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, database: Any, *, timeout_seconds: int = 120) -> None:
        self.database = database
        self.timeout_seconds = timeout_seconds
        self.providers = SharedProviderRegistry()

    def deliver(
        self,
        request: DeliveryAdapterRequest,
        *,
        target: dict,
    ) -> DeliveryAdapterResult:
        if request.platform != "youtube" or target.get("primary_adapter_key") != self.adapter_key:
            raise DeliveryAdapterError(
                "youtube_target_mismatch",
                "The request is not bound to the official YouTube adapter.",
                retryable=False,
            )
        if target.get("simulated") or not target.get("execution_enabled"):
            raise DeliveryAdapterError(
                "youtube_execution_not_enabled",
                "The YouTube target is not enabled for official execution.",
                retryable=False,
            )

        configuration = dict(target.get("configuration") or {})
        self._require_privacy_authorization(request.privacy, configuration)
        credentials = self._credentials(target)
        access_token = self._access_token(credentials)
        media_path, mime_type, size_bytes = self._local_output(request)

        metadata = request.metadata
        title = str(metadata.get("title") or "").strip()
        caption = str(metadata.get("caption") or "").strip()
        hashtags = [str(item).strip().lstrip("#") for item in metadata.get("hashtags") or []]
        disclosure = str(metadata.get("disclosure_text") or "").strip()
        description_parts = [caption]
        if hashtags:
            description_parts.append(" ".join(f"#{tag}" for tag in hashtags))
        if disclosure:
            description_parts.append(disclosure)
        description = "\n\n".join(part for part in description_parts if part)

        status: dict[str, Any] = {
            "privacyStatus": request.privacy.value,
            "selfDeclaredMadeForKids": bool(configuration.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(configuration.get("contains_synthetic_media", True)),
            "embeddable": bool(configuration.get("embeddable", True)),
            "license": str(configuration.get("license", "youtube")),
        }
        scheduled_for = metadata.get("scheduled_for")
        if scheduled_for:
            if request.privacy is not DeliveryPrivacy.PRIVATE:
                raise DeliveryAdapterError(
                    "youtube_schedule_requires_private",
                    "YouTube scheduled publishing requires private upload status.",
                    retryable=False,
                )
            if not configuration.get("allow_public", False):
                raise DeliveryAdapterError(
                    "youtube_public_not_authorized",
                    "Scheduled public publishing is not authorized for this target.",
                    retryable=False,
                )
            status["publishAt"] = str(scheduled_for)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": hashtags,
                "categoryId": str(configuration.get("category_id", "22")),
                "defaultLanguage": str(configuration.get("default_language", "en")),
            },
            "status": status,
        }
        notify = "true" if bool(configuration.get("notify_subscribers", False)) else "false"
        initiation_url = f"{self.upload_url}&notifySubscribers={notify}"
        initiation = Request(
            initiation_url,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(size_bytes),
                "X-Upload-Content-Type": mime_type,
            },
        )
        response = self._open(initiation, operation="youtube_upload_initialize")
        upload_location = response.headers.get("Location")
        response.close()
        if not upload_location or urlparse(upload_location).scheme != "https":
            raise DeliveryAdapterError(
                "youtube_upload_session_missing",
                "YouTube did not return a secure resumable upload session.",
                retryable=True,
            )

        try:
            media = media_path.read_bytes()
        except OSError as exc:
            raise DeliveryAdapterError(
                "youtube_media_read_failed",
                "The approved release media could not be read.",
                retryable=False,
            ) from exc
        upload = Request(
            upload_location,
            data=media,
            method="PUT",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": mime_type,
                "Content-Length": str(size_bytes),
            },
        )
        completed = self._open(upload, operation="youtube_upload_media")
        try:
            payload = json.loads(completed.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeliveryAdapterError(
                "youtube_upload_response_invalid",
                "YouTube returned an invalid upload response.",
                retryable=True,
            ) from exc
        finally:
            completed.close()

        video_id = str(payload.get("id") or "").strip()
        if not video_id:
            raise DeliveryAdapterError(
                "youtube_video_id_missing",
                "YouTube accepted the upload without returning a video ID.",
                retryable=True,
            )
        platform_reference = f"https://www.youtube.com/watch?v={video_id}"
        return DeliveryAdapterResult(
            provider_request_id=video_id,
            platform_reference=platform_reference,
            response_payload={
                "adapter": self.adapter_key,
                "video_id": video_id,
                "platform_reference": platform_reference,
                "privacy_status": request.privacy.value,
                "scheduled_for": scheduled_for,
                "release_manifest_hash": request.release_manifest_hash,
                "output_asset_sha256": request.output_asset_sha256,
                "synthetic_media_disclosed": bool(status["containsSyntheticMedia"]),
            },
        )

    def reconcile(
        self,
        request: DeliveryAdapterRequest,
        *,
        platform_reference: str,
        target: dict,
    ) -> DeliveryReconciliationResult:
        video_id = self._video_id(platform_reference)
        credentials = self._credentials(target)
        access_token = self._access_token(credentials)
        query = urlencode({"part": "status", "id": video_id})
        call = Request(
            f"{self.video_status_url}?{query}",
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response = self._open(call, operation="youtube_status")
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeliveryAdapterError(
                "youtube_status_response_invalid",
                "YouTube returned an invalid status response.",
                retryable=True,
            ) from exc
        finally:
            response.close()
        items = payload.get("items") or []
        if not items:
            platform_status = DeliveryPlatformStatus.DELETED
            status_payload: Mapping[str, Any] = {}
        else:
            status_payload = dict(items[0].get("status") or {})
            upload_status = str(status_payload.get("uploadStatus") or "")
            privacy = str(status_payload.get("privacyStatus") or "")
            if upload_status in {"failed", "rejected"}:
                platform_status = DeliveryPlatformStatus.FAILED
            elif status_payload.get("publishAt"):
                platform_status = DeliveryPlatformStatus.SCHEDULED
            elif privacy == "public":
                platform_status = DeliveryPlatformStatus.PUBLISHED
            elif privacy in {"private", "unlisted"}:
                platform_status = DeliveryPlatformStatus.DRAFT
            else:
                platform_status = DeliveryPlatformStatus.UNKNOWN
        return DeliveryReconciliationResult(
            platform_status=platform_status,
            response_payload={
                "adapter": self.adapter_key,
                "video_id": video_id,
                "platform_reference": platform_reference,
                "platform_status": platform_status.value,
                "youtube_status": dict(status_payload),
                "release_manifest_hash": request.release_manifest_hash,
            },
        )

    def _credentials(self, target: Mapping[str, Any]) -> dict[str, str]:
        reference = str(target.get("credential_secret_ref") or "")
        if not reference.startswith("env:"):
            raise DeliveryAdapterError(
                "youtube_credential_reference_invalid",
                "YouTube credentials must be referenced through an environment variable.",
                retryable=False,
            )
        environment_key = reference.removeprefix("env:").strip()
        credential_path = os.getenv(environment_key)
        if not credential_path:
            raise DeliveryAdapterError(
                "youtube_credentials_unavailable",
                "The referenced YouTube credential file is unavailable.",
                retryable=False,
            )
        path = Path(credential_path).expanduser().resolve()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeliveryAdapterError(
                "youtube_credentials_unreadable",
                "The referenced YouTube credential file could not be read.",
                retryable=False,
            ) from exc
        required = ("client_id", "client_secret", "refresh_token")
        credentials = {key: str(raw.get(key) or "") for key in required}
        if any(not credentials[key] for key in required):
            raise DeliveryAdapterError(
                "youtube_credentials_incomplete",
                "The YouTube credential reference is incomplete.",
                retryable=False,
            )
        return credentials

    def _access_token(self, credentials: Mapping[str, str]) -> str:
        data = urlencode(
            {
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
                "refresh_token": credentials["refresh_token"],
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        call = Request(
            self.token_url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = self._open(call, operation="youtube_oauth_refresh")
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeliveryAdapterError(
                "youtube_oauth_response_invalid",
                "Google returned an invalid OAuth response.",
                retryable=True,
            ) from exc
        finally:
            response.close()
        token = str(payload.get("access_token") or "")
        if not token:
            raise DeliveryAdapterError(
                "youtube_oauth_token_missing",
                "Google OAuth did not return an access token.",
                retryable=True,
            )
        return token

    def _local_output(self, request: DeliveryAdapterRequest) -> tuple[Path, str, int]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT sso.object_key,sso.sha256,sso.size_bytes,sso.mime_type,
                          ssb.backend_key,ssb.driver,ssb.environment,ssb.endpoint_url,
                          ssb.bucket_name,ssb.base_prefix,ssb.region,ssb.credential_secret_ref,
                          ssb.configuration
                   FROM football_brief.shared_artifact_object_roles role
                   JOIN football_brief.shared_storage_objects sso ON sso.id=role.storage_object_id
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE role.artifact_version_id=%s AND role.role='original'
                     AND sso.status='available' AND ssb.status='active'""",
                (request.output_artifact_version_id,),
            ).fetchone()
        if not row:
            raise DeliveryAdapterError(
                "youtube_output_object_unavailable",
                "The approved release output is not available in shared storage.",
                retryable=False,
            )
        backend = dict(row)
        try:
            provider = self.providers.provider(backend)
            target = provider.access_target(
                object_key=str(row["object_key"]),
                expires_in_seconds=900,
                mime_type=row["mime_type"],
                filename=None,
            )
        except SharedStorageError as exc:
            raise DeliveryAdapterError(
                "youtube_output_resolution_failed",
                "The approved release output could not be resolved from shared storage.",
                retryable=False,
            ) from exc
        if target.kind != "file":
            raise DeliveryAdapterError(
                "youtube_local_output_required",
                "The first official YouTube adapter requires a locally readable shared artifact.",
                retryable=False,
            )
        path = Path(target.value).expanduser().resolve(strict=True)
        inspected = inspect_file(path)
        if inspected.sha256 != request.output_asset_sha256 or inspected.sha256 != row["sha256"]:
            raise DeliveryAdapterError(
                "youtube_output_checksum_mismatch",
                "The approved release output checksum does not match canonical evidence.",
                retryable=False,
            )
        if inspected.size_bytes != int(row["size_bytes"]):
            raise DeliveryAdapterError(
                "youtube_output_size_mismatch",
                "The approved release output size does not match canonical evidence.",
                retryable=False,
            )
        mime_type = str(row["mime_type"] or mimetypes.guess_type(path.name)[0] or "video/mp4")
        if not mime_type.startswith("video/"):
            raise DeliveryAdapterError(
                "youtube_output_not_video",
                "The approved release output is not a video media type.",
                retryable=False,
            )
        return path, mime_type, inspected.size_bytes

    @staticmethod
    def _require_privacy_authorization(
        privacy: DeliveryPrivacy,
        configuration: Mapping[str, Any],
    ) -> None:
        if privacy is DeliveryPrivacy.PUBLIC and not configuration.get("allow_public", False):
            raise DeliveryAdapterError(
                "youtube_public_not_authorized",
                "Public YouTube publishing is not authorized for this target.",
                retryable=False,
            )
        if privacy is DeliveryPrivacy.UNLISTED and not configuration.get("allow_unlisted", False):
            raise DeliveryAdapterError(
                "youtube_unlisted_not_authorized",
                "Unlisted YouTube publishing is not authorized for this target.",
                retryable=False,
            )

    @staticmethod
    def _video_id(platform_reference: str) -> str:
        parsed = urlparse(platform_reference)
        if parsed.netloc not in {"www.youtube.com", "youtube.com", "youtu.be"}:
            raise DeliveryAdapterError(
                "youtube_reference_invalid",
                "The platform reference is not a YouTube video URL.",
                retryable=False,
            )
        if parsed.netloc == "youtu.be":
            video_id = parsed.path.strip("/")
        else:
            query = dict(item.split("=", 1) for item in parsed.query.split("&") if "=" in item)
            video_id = query.get("v", "")
        if not video_id:
            raise DeliveryAdapterError(
                "youtube_reference_invalid",
                "The YouTube platform reference has no video ID.",
                retryable=False,
            )
        return video_id

    def _open(self, request: Request, *, operation: str):
        try:
            # Requests are limited to the hard-coded Google HTTPS endpoints or the HTTPS resumable session returned by YouTube.
            return urlopen(request, timeout=self.timeout_seconds)  # nosec B310
        except HTTPError as exc:
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            raise DeliveryAdapterError(
                f"{operation}_http_{exc.code}",
                f"The official YouTube API rejected {operation}.",
                retryable=retryable,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise DeliveryAdapterError(
                f"{operation}_unavailable",
                f"The official YouTube API was unavailable during {operation}.",
                retryable=True,
            ) from exc
