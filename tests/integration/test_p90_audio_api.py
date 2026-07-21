from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p90_audio_support import p89_database, p89_seeded, p90_ready


pytestmark = pytest.mark.integration


def audio_client(database, ready) -> TestClient:
    brand_one = str(ready["brand_one"])
    brand_two = str(ready["brand_two"])
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["outsider"]: OperatorIdentity(
            operator_id=str(ready["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
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


def test_audio_api_enforces_roles_brand_scope_and_local_defaults(p89_database, p90_ready) -> None:
    client = audio_client(p89_database, p90_ready)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    admin = {"X-Operator-Key": "admin-key"}
    payload = {
        "model_id": "kokoro-v1.0",
        "timeout_seconds": 300,
        "max_attempts": 3,
    }

    reviewer_initialize = client.post(
        f"/audio/content/{p90_ready['content_one']}",
        headers=reviewer,
        json=payload,
    )
    assert reviewer_initialize.status_code == 403

    outsider_initialize = client.post(
        f"/audio/content/{p90_ready['content_one']}",
        headers=outsider,
        json=payload,
    )
    assert outsider_initialize.status_code == 403

    initialized = client.post(
        f"/audio/content/{p90_ready['content_one']}",
        headers=producer,
        json=payload,
    )
    assert initialized.status_code == 200, initialized.text
    body = initialized.json()
    production_id = body["production"]["id"]
    assert body["production"]["provider"] == "kokoro-onnx"
    assert body["production"]["model_id"] == "kokoro-v1.0"
    assert all(float(take["actual_cost_usd"]) == 0 for take in body["takes"])
    assert all(take["external_fee_incurred"] is False for take in body["takes"])

    reviewer_read = client.get(f"/audio/{production_id}", headers=reviewer)
    assert reviewer_read.status_code == 200

    admin_read = client.get(f"/audio/{production_id}", headers=admin)
    assert admin_read.status_code == 200

    outsider_read = client.get(f"/audio/{production_id}", headers=outsider)
    assert outsider_read.status_code == 403

    reviewer_pronunciation = client.post(
        f"/audio/{production_id}/pronunciations",
        headers=reviewer,
        json={
            "expected_lock_version": body["production"]["lock_version"],
            "token": "octopus",
            "pronunciation": "OK-tuh-pus",
            "locale": "en-US",
        },
    )
    assert reviewer_pronunciation.status_code == 403

    producer_decision = client.post(
        f"/audio/{production_id}/decisions",
        headers=producer,
        json={
            "expected_lock_version": body["production"]["lock_version"],
            "decision": "approved",
            "rationale": "A producer cannot approve their own local audio evidence.",
        },
    )
    assert producer_decision.status_code == 403

    producer_assembly_before_approval = client.post(
        f"/audio/{production_id}/assembly",
        headers=producer,
        json={
            "expected_lock_version": body["production"]["lock_version"],
            "model_id": "local-ffmpeg",
        },
    )
    assert producer_assembly_before_approval.status_code == 409
    assert producer_assembly_before_approval.json()["detail"]["code"] == "approved_audio_mix_required"
