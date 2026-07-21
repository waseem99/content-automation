from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from src.application.shared_storage.models import ArtifactVersionRequest
from src.application.shared_storage.service import _utcnow
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p95_shared_storage_support import p93_database, p93_seeded, p95_ready
from tests.integration.test_p96_final_release_lifecycle import release_profile


pytestmark = pytest.mark.integration


def release_client(database, ready) -> TestClient:
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Release Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Release Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Release Reviewer",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["outsider"]: OperatorIdentity(
            operator_id=str(ready["outsider"]),
            key_name="outsider-key",
            display_name="Other Brand Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_two"])}),
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
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=OperatorRuntimeSettings(_env_file=None, database_require_schema=False),
        )
    )


def create_api_artifact(ready, *, key: str, kind: str, asset_key: str):
    return ready["service"].create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=ready["brand_one"],
            portfolio_content_id=ready["content_one"],
            content_version=ready["content_one_version"],
            artifact_key=key,
            artifact_kind=kind,
            original_asset_id=ready["assets"][asset_key],
            backend_id=ready["shared_backend"]["id"],
            retention_until=_utcnow() + timedelta(days=60),
            metadata={"phase": "P96", "api_fixture": True},
        ),
        actor=ready["producer"],
    )["artifact"]


def test_release_api_separates_admin_producer_reviewer_and_brand_access(
    p93_database,
    p95_ready,
) -> None:
    client = release_client(p93_database, p95_ready)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}

    profile_payload = release_profile().model_dump(mode="json")
    assert client.post("/release-profiles", headers=producer, json=profile_payload).status_code == 403
    created_profile = client.post("/release-profiles", headers=admin, json=profile_payload)
    assert created_profile.status_code == 200, created_profile.text
    profile_id = created_profile.json()["profile"]["id"]
    activated = client.post(f"/release-profiles/{profile_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text

    narration = create_api_artifact(
        p95_ready,
        key="api-release/narration",
        kind="voiceover",
        asset_key="proxy",
    )
    visual = create_api_artifact(
        p95_ready,
        key="api-release/visual",
        kind="premium_clip",
        asset_key="original",
    )
    branding = create_api_artifact(
        p95_ready,
        key="api-release/branding",
        kind="thumbnail",
        asset_key="thumbnail",
    )
    for artifact, role in (
        (narration, "narration"),
        (visual, "visual_shot"),
        (branding, "branding"),
    ):
        denied = client.post(
            "/release-input-decisions",
            headers=outsider,
            json={
                "artifact_version_id": artifact["id"],
                "role": role,
                "decision": "approved",
                "rationale": "Wrong brand reviewer must not approve this artifact.",
            },
        )
        assert denied.status_code == 403
        approved = client.post(
            "/release-input-decisions",
            headers=reviewer,
            json={
                "artifact_version_id": artifact["id"],
                "role": role,
                "decision": "approved",
                "rationale": f"The exact {role} input is approved for API release testing.",
            },
        )
        assert approved.status_code == 200, approved.text

    release_payload = {
        "portfolio_content_id": str(p95_ready["content_one"]),
        "content_version": int(p95_ready["content_one_version"]),
        "render_profile_id": profile_id,
        "inputs": [
            {"artifact_version_id": str(narration["id"]), "role": "narration", "sequence_number": 0},
            {"artifact_version_id": str(visual["id"]), "role": "visual_shot", "sequence_number": 1},
            {"artifact_version_id": str(branding["id"]), "role": "branding", "sequence_number": 0},
        ],
        "metadata": {"source": "p96-api"},
    }
    assert client.post("/releases", headers=outsider, json=release_payload).status_code == 403
    created = client.post("/releases", headers=producer, json=release_payload)
    assert created.status_code == 200, created.text
    release_id = created.json()["release"]["id"]

    assert client.get(f"/releases/{release_id}", headers=outsider).status_code == 403
    assert client.post(
        f"/releases/{release_id}/assembly",
        headers=reviewer,
        json={"max_attempts": 2},
    ).status_code == 403
    enqueued = client.post(
        f"/releases/{release_id}/assembly",
        headers=producer,
        json={"preferred_worker_id": p95_ready["producer"], "max_attempts": 2},
    )
    assert enqueued.status_code == 200, enqueued.text
    assert enqueued.json()["release"]["status"] == "assembly_queued"
    assert enqueued.json()["job"]["job_type"] == "assembly"
