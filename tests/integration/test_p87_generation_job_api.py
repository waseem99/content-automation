from __future__ import annotations

from fastapi.testclient import TestClient

from src.infrastructure.database.connection import Database
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded


__all__ = ["database", "seeded"]


def client_for(database: Database, seeded: dict[str, object]) -> TestClient:
    brand_id = str(seeded["brand_id"])
    identities = {
        str(seeded["admin"]): OperatorIdentity(
            operator_id=str(seeded["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        str(seeded["producer"]): OperatorIdentity(
            operator_id=str(seeded["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
        str(seeded["publisher"]): OperatorIdentity(
            operator_id=str(seeded["publisher"]),
            key_name="publisher-key",
            display_name="Publisher One",
            roles=frozenset({OperatorRole.PUBLISHER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
        str(seeded["reviewer"]): OperatorIdentity(
            operator_id=str(seeded["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_id}),
            active=True,
        ),
        str(seeded["outsider"]): OperatorIdentity(
            operator_id=str(seeded["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset(),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(seeded["admin"]),
            "producer-key": str(seeded["producer"]),
            "publisher-key": str(seeded["publisher"]),
            "reviewer-key": str(seeded["reviewer"]),
            "outsider-key": str(seeded["outsider"]),
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


def enqueue_payload(seeded: dict[str, object], *, job_type: str, key: str) -> dict:
    return {
        "portfolio_content_id": str(seeded["content_id"]),
        "content_version": 1,
        "job_type": job_type,
        "provider": "facebook" if job_type == "publishing" else "p68-local",
        "model_id": "api-test-v1",
        "idempotency_key": key,
        "input_payload": {"request": key},
        "timeout_seconds": 120,
        "max_attempts": 2,
    }


def test_producer_and_publisher_job_types_are_role_separated_and_brand_scoped(
    database: Database, seeded: dict[str, object]
) -> None:
    client = client_for(database, seeded)
    producer = {"X-Operator-Key": "producer-key"}
    publisher = {"X-Operator-Key": "publisher-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}

    keyframe = client.post(
        "/generation/jobs",
        headers=producer,
        json=enqueue_payload(
            seeded,
            job_type="keyframe",
            key="p87:api:producer-keyframe",
        ),
    )
    assert keyframe.status_code == 200, keyframe.text
    keyframe_id = keyframe.json()["job"]["id"]

    publisher_denied = client.post(
        "/generation/jobs",
        headers=publisher,
        json=enqueue_payload(
            seeded,
            job_type="keyframe",
            key="p87:api:publisher-keyframe-denied",
        ),
    )
    assert publisher_denied.status_code == 403

    reviewer_denied = client.post(
        "/generation/jobs",
        headers=reviewer,
        json=enqueue_payload(
            seeded,
            job_type="keyframe",
            key="p87:api:reviewer-keyframe-denied",
        ),
    )
    assert reviewer_denied.status_code == 403

    outsider_denied = client.post(
        "/generation/jobs",
        headers=outsider,
        json=enqueue_payload(
            seeded,
            job_type="keyframe",
            key="p87:api:outsider-brand-denied",
        ),
    )
    assert outsider_denied.status_code == 403

    publishing = client.post(
        "/generation/jobs",
        headers=publisher,
        json=enqueue_payload(
            seeded,
            job_type="publishing",
            key="p87:api:publisher-delivery",
        ),
    )
    assert publishing.status_code == 200, publishing.text
    publishing_id = publishing.json()["job"]["id"]

    producer_claim = client.post(
        "/generation/jobs/claim",
        headers=producer,
        json={"job_types": ["keyframe"], "lease_seconds": 120},
    )
    assert producer_claim.status_code == 200, producer_claim.text
    assert producer_claim.json()["claim"]["job"]["id"] == keyframe_id

    producer_publish_claim = client.post(
        "/generation/jobs/claim",
        headers=producer,
        json={"job_types": ["publishing"], "lease_seconds": 120},
    )
    assert producer_publish_claim.status_code == 403

    publisher_claim = client.post(
        "/generation/jobs/claim",
        headers=publisher,
        json={"job_types": ["publishing"], "lease_seconds": 120},
    )
    assert publisher_claim.status_code == 200, publisher_claim.text
    assert publisher_claim.json()["claim"]["job"]["id"] == publishing_id

    producer_queue = client.get("/generation/jobs", headers=producer)
    assert producer_queue.status_code == 200
    assert {item["id"] for item in producer_queue.json()["items"]} == {
        keyframe_id,
        publishing_id,
    }

    outsider_queue = client.get("/generation/jobs", headers=outsider)
    assert outsider_queue.status_code == 200
    assert outsider_queue.json()["items"] == []


def test_claim_identity_and_lease_token_cannot_be_reused_by_another_operator(
    database: Database, seeded: dict[str, object]
) -> None:
    client = client_for(database, seeded)
    producer = {"X-Operator-Key": "producer-key"}
    admin = {"X-Operator-Key": "admin-key"}

    enqueued = client.post(
        "/generation/jobs",
        headers=producer,
        json=enqueue_payload(
            seeded,
            job_type="preview",
            key="p87:api:claim-owner",
        ),
    )
    assert enqueued.status_code == 200, enqueued.text
    job_id = enqueued.json()["job"]["id"]

    claimed = client.post(
        "/generation/jobs/claim",
        headers=producer,
        json={"job_types": ["preview"], "lease_seconds": 120},
    )
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()["claim"]

    wrong_worker = client.post(
        f"/generation/jobs/{job_id}/complete",
        headers=admin,
        json={
            "attempt_id": claim["attempt"]["id"],
            "lease_token": claim["lease_token"],
            "output_payload": {"asset_id": "must-not-register"},
        },
    )
    assert wrong_worker.status_code == 403
    assert wrong_worker.json()["detail"]["code"] == "generation_job_worker_mismatch"

    completed = client.post(
        f"/generation/jobs/{job_id}/complete",
        headers=producer,
        json={
            "attempt_id": claim["attempt"]["id"],
            "lease_token": claim["lease_token"],
            "output_payload": {"asset_id": "preview-asset-1"},
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["job"]["status"] == "succeeded"
