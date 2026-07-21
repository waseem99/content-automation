from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p95_shared_storage_support import (
    p93_database,
    p93_seeded,
    p95_ready,
)


pytestmark = pytest.mark.integration


def shared_storage_client(database, ready) -> TestClient:
    brand_one = str(ready["brand_one"])
    brand_two = str(ready["brand_two"])
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Renderer Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Renderer Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Renderer Reviewer",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["outsider"]: OperatorIdentity(
            operator_id=str(ready["outsider"]),
            key_name="outsider-key",
            display_name="Other Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_two}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(ready["admin"]),
            "producer-key": str(ready["producer"]),
            "reviewer-key": str(ready["reviewer"]),
            "outsider-key": str(ready["outsider"]),
        },
        identities=identities,
    )
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=runtime,
        )
    )


def test_remote_reviewer_can_stream_signed_proxy_without_shared_filesystem(
    p93_database,
    p95_ready,
) -> None:
    client = shared_storage_client(p93_database, p95_ready)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    admin = {"X-Operator-Key": "admin-key"}

    payload = {
        "brand_id": str(p95_ready["brand_one"]),
        "portfolio_content_id": str(p95_ready["content_one"]),
        "content_version": int(p95_ready["content_one_version"]),
        "artifact_key": "api/final-video",
        "artifact_kind": "final_video",
        "original_asset_id": str(p95_ready["assets"]["original"]),
        "review_proxy_asset_id": str(p95_ready["assets"]["proxy"]),
        "thumbnail_asset_id": str(p95_ready["assets"]["thumbnail"]),
        "backend_id": str(p95_ready["shared_backend"]["id"]),
        "retention_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "metadata": {"source": "p95-api-test"},
    }
    assert client.post("/storage/artifacts", headers=reviewer, json=payload).status_code == 403
    assert client.post("/storage/artifacts", headers=outsider, json=payload).status_code == 403
    created_response = client.post("/storage/artifacts", headers=producer, json=payload)
    assert created_response.status_code == 200, created_response.text
    artifact = created_response.json()["artifact"]

    assert client.get(f"/storage/artifacts/{artifact['id']}", headers=outsider).status_code == 403
    reviewer_detail = client.get(f"/storage/artifacts/{artifact['id']}", headers=reviewer)
    assert reviewer_detail.status_code == 200, reviewer_detail.text
    assert {item["role"] for item in reviewer_detail.json()["objects"]} == {
        "original", "review_proxy", "thumbnail"
    }

    outsider_access = client.post(
        f"/storage/artifacts/{artifact['id']}/access",
        headers=outsider,
        json={"role": "review_proxy", "expires_in_seconds": 300, "access_purpose": "review"},
    )
    assert outsider_access.status_code == 403

    issued = client.post(
        f"/storage/artifacts/{artifact['id']}/access",
        headers=reviewer,
        json={
            "role": "review_proxy",
            "expires_in_seconds": 300,
            "issued_to_operator_id": p95_ready["reviewer"],
            "access_purpose": "review",
        },
    )
    assert issued.status_code == 200, issued.text
    access = issued.json()["access"]
    signed_path = urlsplit(access["url"]).path + "?" + urlsplit(access["url"]).query

    streamed = client.get(signed_path)
    assert streamed.status_code == 200, streamed.text
    assert streamed.content == p95_ready["paths"]["proxy"].read_bytes()
    assert streamed.headers["content-type"].startswith("video/")

    invalid = client.get(f"/shared-media/{access['grant_id']}?token=invalid")
    assert invalid.status_code == 403
    with p93_database.connection() as conn:
        invalid_events = conn.execute(
            """SELECT event,details FROM football_brief.shared_access_events
               WHERE grant_id=%s ORDER BY created_at,id""",
            (access["grant_id"],),
        ).fetchall()
    assert [row["event"] for row in invalid_events] == ["issued", "accessed", "denied"]
    assert invalid_events[-1]["details"]["error_code"] == "access_token_invalid"

    revoked = client.post(f"/storage/access/{access['grant_id']}/revoke", headers=reviewer)
    assert revoked.status_code == 200, revoked.text
    after_revoke = client.get(signed_path)
    assert after_revoke.status_code == 410
    with p93_database.connection() as conn:
        revoked_events = conn.execute(
            """SELECT event,details FROM football_brief.shared_access_events
               WHERE grant_id=%s ORDER BY created_at,id""",
            (access["grant_id"],),
        ).fetchall()
    assert [row["event"] for row in revoked_events] == [
        "issued", "accessed", "denied", "revoked", "denied"
    ]
    assert revoked_events[-1]["details"]["error_code"] == "access_grant_revoked"

    listed = client.get(
        f"/storage/artifacts?brand_id={p95_ready['brand_one']}&include_history=true",
        headers=reviewer,
    )
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == artifact["id"] for item in listed.json()["artifacts"])

    backends = client.get("/storage/backends", headers=admin)
    assert backends.status_code == 200
    assert {item["backend_key"] for item in backends.json()["backends"]} >= {
        "shared-test", "shared-restore"
    }
