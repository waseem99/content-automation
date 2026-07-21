from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def script_client(database, seeded) -> TestClient:
    brand_one = str(seeded["brand_one"])
    brand_two = str(seeded["brand_two"])
    identities = {
        seeded["admin"]: OperatorIdentity(
            operator_id=str(seeded["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        seeded["producer"]: OperatorIdentity(
            operator_id=str(seeded["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        seeded["reviewer"]: OperatorIdentity(
            operator_id=str(seeded["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        seeded["outsider"]: OperatorIdentity(
            operator_id=str(seeded["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_two}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(seeded["admin"]),
            "producer-key": str(seeded["producer"]),
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


def generation_payload() -> dict:
    return {
        "platform": "facebook",
        "format": "vertical_short",
        "language": "en-US",
        "target_duration_seconds": 60,
        "words_per_minute": 150,
        "duration_tolerance_percent": 10,
        "seed": 91,
        "adapter_mode": "deterministic",
    }


def test_script_api_enforces_producer_reviewer_and_brand_boundaries(
    p89_database, p89_seeded
) -> None:
    client = script_client(p89_database, p89_seeded)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}

    reviewer_generate = client.post(
        f"/scripts/content/{p89_seeded['content_one']}",
        headers=reviewer,
        json=generation_payload(),
    )
    assert reviewer_generate.status_code == 403

    outsider_generate = client.post(
        f"/scripts/content/{p89_seeded['content_one']}",
        headers=outsider,
        json=generation_payload(),
    )
    assert outsider_generate.status_code == 403

    generated = client.post(
        f"/scripts/content/{p89_seeded['content_one']}",
        headers=producer,
        json=generation_payload(),
    )
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    document_id = payload["document"]["id"]
    version_id = payload["document"]["current_version_id"]
    narration_section = next(
        section for section in payload["sections"]
        if section["section_type"] == "narration"
    )

    outsider_read = client.get(f"/scripts/{document_id}", headers=outsider)
    assert outsider_read.status_code == 403

    producer_decision = client.post(
        f"/scripts/{document_id}/decisions",
        headers=producer,
        json={
            "expected_lock_version": 1,
            "decision": "approved",
            "rationale": "Producer cannot approve their own script.",
        },
    )
    assert producer_decision.status_code == 403

    submitted = client.post(
        f"/scripts/{document_id}/submit",
        headers=producer,
        json={"expected_lock_version": 1},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["document"]["lock_version"] == 2
    assert submitted.json()["document"]["current_version_status"] == "in_review"

    producer_action = client.post(
        f"/scripts/{document_id}/review-actions",
        headers=producer,
        json={
            "expected_lock_version": 2,
            "action": {
                "script_version_id": version_id,
                "script_section_id": narration_section["id"],
                "action_type": "source_request",
                "body": "Producer cannot create reviewer actions.",
            },
        },
    )
    assert producer_action.status_code == 403

    reviewer_action = client.post(
        f"/scripts/{document_id}/review-actions",
        headers=reviewer,
        json={
            "expected_lock_version": 2,
            "action": {
                "script_version_id": version_id,
                "script_section_id": narration_section["id"],
                "action_type": "source_request",
                "body": "Add primary evidence and narrow the unsupported factual wording.",
            },
        },
    )
    assert reviewer_action.status_code == 200, reviewer_action.text
    assert reviewer_action.json()["document"]["lock_version"] == 3

    changed = client.post(
        f"/scripts/{document_id}/decisions",
        headers=reviewer,
        json={
            "expected_lock_version": 3,
            "decision": "changes_requested",
            "rationale": "Source support is required before approval.",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["document"]["current_version_status"] == "changes_requested"
    assert changed.json()["document"]["lock_version"] == 4

    revised = client.post(
        f"/scripts/{document_id}/revise",
        headers=producer,
        json={
            "expected_lock_version": 4,
            "reason": "Address the source request and preserve the prior review trail.",
        },
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["document"]["current_version"] == 2
    assert revised.json()["document"]["current_version_status"] == "working"
    assert len(revised.json()["review_actions"]) == 1
    assert revised.json()["review_actions"][0]["script_version_id"] == version_id
