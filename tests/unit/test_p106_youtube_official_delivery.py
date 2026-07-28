from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.application.delivery.adapters import DeliveryAdapterError, default_delivery_adapters
from src.application.delivery.models import DeliveryAdapterRequest, DeliveryPrivacy, DeliveryTargetRequest
from src.application.delivery.official_service import OfficialPlatformDeliveryService
from src.application.delivery.youtube import YouTubeOfficialDeliveryAdapter


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0093_youtube_official_delivery.sql"
OAUTH = ROOT / "scripts" / "setup_youtube_oauth.py"
SETUP = ROOT / "scripts" / "windows" / "setup_youtube_official.ps1"


class FakeResponse:
    def __init__(self, payload: dict | None = None, *, headers: dict[str, str] | None = None) -> None:
        self.payload = json.dumps(payload or {}).encode("utf-8")
        self.headers = headers or {}

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        return None


def adapter_request(privacy: DeliveryPrivacy = DeliveryPrivacy.PRIVATE) -> DeliveryAdapterRequest:
    return DeliveryAdapterRequest(
        delivery_request_id=uuid4(),
        delivery_fingerprint="a" * 64,
        platform="youtube",
        target_key="youtube-official-main",
        privacy=privacy,
        release_manifest_hash="b" * 64,
        release_manifest={"version": 1},
        output_artifact_version_id=uuid4(),
        output_asset_sha256="c" * 64,
        metadata={
            "delivery_mode": "immediate",
            "title": "Private review upload",
            "caption": "Approved Content Automation release.",
            "hashtags": ["ContentAutomation"],
            "disclosure_text": "AI-assisted visuals; human reviewed.",
        },
    )


def official_target(**configuration) -> dict:
    return {
        "status": "active",
        "primary_adapter_key": "youtube-official",
        "platform": "youtube",
        "environment": "staging",
        "simulated": False,
        "execution_enabled": True,
        "credential_secret_ref": "env:YOUTUBE_CREDENTIAL_FILE",
        "configuration": {
            "allow_public": False,
            "allow_unlisted": False,
            "notify_subscribers": False,
            "contains_synthetic_media": True,
            **configuration,
        },
    }


def test_target_contract_allows_only_official_account_gated_youtube() -> None:
    target = DeliveryTargetRequest(
        target_key="youtube-official-main",
        display_name="Official YouTube Channel",
        platform="youtube",
        environment="staging",
        target_account_ref="channel:content-automation",
        time_zone="Asia/Karachi",
        primary_adapter_key="youtube-official",
        supported_privacy=(DeliveryPrivacy.PRIVATE,),
        default_privacy=DeliveryPrivacy.PRIVATE,
        credential_secret_ref="env:YOUTUBE_CREDENTIAL_FILE",
        simulated=False,
        execution_enabled=True,
        thumbnail_required=False,
        disclosure_required=True,
    )
    assert target.execution_enabled is True
    assert target.default_privacy is DeliveryPrivacy.PRIVATE

    with pytest.raises(ValidationError):
        DeliveryTargetRequest(
            target_key="unsafe-live-target",
            display_name="Unsafe Live Target",
            platform="facebook",
            environment="production",
            target_account_ref="page:unsafe",
            time_zone="Asia/Karachi",
            primary_adapter_key="unknown-live-adapter",
            supported_privacy=(DeliveryPrivacy.PUBLIC,),
            default_privacy=DeliveryPrivacy.PUBLIC,
            credential_secret_ref="env:UNSAFE_CREDENTIAL",
            simulated=False,
            execution_enabled=True,
        )


def test_default_registry_adds_youtube_only_with_database() -> None:
    assert "youtube-official" not in default_delivery_adapters()
    assert isinstance(default_delivery_adapters(object())["youtube-official"], YouTubeOfficialDeliveryAdapter)


def test_private_upload_uses_resumable_session_and_records_video_id(tmp_path: Path) -> None:
    media = tmp_path / "approved.mp4"
    media.write_bytes(b"approved-video")
    adapter = YouTubeOfficialDeliveryAdapter(object())
    adapter._credentials = lambda target: {  # type: ignore[method-assign]
        "client_id": "client",
        "client_secret": "secret",
        "refresh_token": "refresh",
    }
    adapter._access_token = lambda credentials: "access-token"  # type: ignore[method-assign]
    adapter._local_output = lambda request: (media, "video/mp4", media.stat().st_size)  # type: ignore[method-assign]
    responses = iter(
        [
            FakeResponse(headers={"Location": "https://upload.youtube.test/session/one"}),
            FakeResponse({"id": "video123", "status": {"privacyStatus": "private"}}),
        ]
    )
    adapter._open = lambda request, operation: next(responses)  # type: ignore[method-assign]

    result = adapter.deliver(adapter_request(), target=official_target())
    assert result.provider_request_id == "video123"
    assert result.platform_reference == "https://www.youtube.com/watch?v=video123"
    assert result.response_payload["privacy_status"] == "private"
    assert result.response_payload["synthetic_media_disclosed"] is True


def test_public_upload_is_blocked_until_target_explicitly_allows_it() -> None:
    adapter = YouTubeOfficialDeliveryAdapter(object())
    with pytest.raises(DeliveryAdapterError) as blocked:
        adapter.deliver(adapter_request(DeliveryPrivacy.PUBLIC), target=official_target(allow_public=False))
    assert blocked.value.code == "youtube_public_not_authorized"


def test_official_service_keeps_simulated_and_youtube_boundaries() -> None:
    assert OfficialPlatformDeliveryService._target_is_executable(
        {
            "status": "active",
            "execution_enabled": True,
            "simulated": True,
            "primary_adapter_key": "simulated-primary",
            "platform": "test",
            "credential_secret_ref": None,
            "environment": "test",
        }
    )
    assert OfficialPlatformDeliveryService._target_is_executable(official_target())
    assert not OfficialPlatformDeliveryService._target_is_executable(
        {**official_target(), "primary_adapter_key": "unknown-live-adapter"}
    )


def test_migration_and_setup_preserve_the_live_safety_boundary() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    oauth = OAUTH.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    assert "legacy simulated-only delivery target check" in migration
    assert "primary_adapter_key='youtube-official'" in migration
    assert "credential_secret_ref IS NOT NULL" in migration
    assert "DROP TABLE" not in migration and "DELETE FROM" not in migration
    assert "code_challenge_method" in oauth
    assert "access_type" in oauth and "offline" in oauth
    assert "refresh_token" in oauth
    assert 'Join-Path $Runtime "youtube-oauth.json"' in setup
    assert 'credential_secret_ref = "env:YOUTUBE_CREDENTIAL_FILE"' in setup
    assert "default_privacy = \"private\"" in setup
    assert "upload_executed = $false" in setup
    assert "client_secret=" not in setup and "refresh_token=" not in setup
