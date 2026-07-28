from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import candidate_checks, p91_ready, project_request


pytestmark = pytest.mark.integration


def visual_client(database, ready) -> TestClient:
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


def test_visual_api_enforces_roles_brand_scope_and_local_defaults(p89_database, p91_ready) -> None:
    client = visual_client(p89_database, p91_ready)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    admin = {"X-Operator-Key": "admin-key"}
    payload = project_request(p91_ready).model_dump(mode="json")

    reviewer_initialize = client.post(
        f"/visuals/content/{p91_ready['content_one']}",
        headers=reviewer,
        json=payload,
    )
    assert reviewer_initialize.status_code == 200, reviewer_initialize.text

    outsider_initialize = client.post(
        f"/visuals/content/{p91_ready['content_one']}",
        headers=outsider,
        json=payload,
    )
    assert outsider_initialize.status_code == 403

    initialized = client.post(
        f"/visuals/content/{p91_ready['content_one']}",
        headers=producer,
        json=payload,
    )
    assert initialized.status_code == 200, initialized.text
    body = initialized.json()
    project_id = body["project"]["id"]
    assert body["project"]["provider"] == "comfyui-sdxl-local"
    assert body["project"]["candidate_count"] == 3
    assert len(body["candidates"]) == len(body["shots"]) * 3
    assert all(float(item["actual_cost_usd"]) == 0 for item in body["candidates"])
    assert all(item["external_fee_incurred"] is False for item in body["candidates"])

    assert client.get(f"/visuals/{project_id}", headers=reviewer).status_code == 200
    assert client.get(f"/visuals/{project_id}", headers=admin).status_code == 200
    assert client.get(f"/visuals/{project_id}", headers=outsider).status_code == 403

    own_presets = client.get(
        f"/visual-presets/profiles/{p91_ready['profile_one']}",
        headers=producer,
    )
    assert own_presets.status_code == 200
    assert any(item["id"] == str(p91_ready["visual_preset_id"]) for item in own_presets.json()["presets"])
    assert client.get(
        f"/visual-presets/profiles/{p91_ready['profile_one']}",
        headers=outsider,
    ).status_code == 403

    producer_create_preset = client.post(
        f"/visual-presets/profiles/{p91_ready['profile_one']}",
        headers=producer,
        json={
            "preset_key": "producer-denied",
            "display_name": "Producer Denied",
            "palette": {},
            "subject_rules": {},
            "environment_rules": {},
            "camera_rules": {},
            "lighting_rules": {},
            "framing_rules": {},
            "negative_prompt": "",
            "exclusions": [],
        },
    )
    assert producer_create_preset.status_code == 403

    first_shot = body["shots"][0]
    first_candidate = next(
        item
        for item in body["candidates"]
        if item["visual_shot_version_id"] == first_shot["current_version_id"]
    )
    candidate_id = first_candidate["id"]
    valid_result = {
        "asset_id": str(p91_ready["reference_asset_id"]),
        "width": 704,
        "height": 1280,
        "mime_type": "image/png",
        "provenance": {"local": True, "external_fee_incurred": False},
        "checks": [item.model_dump(mode="json") for item in candidate_checks()],
    }

    reviewer_result = client.post(
        f"/visuals/candidates/{candidate_id}/result",
        headers=reviewer,
        json=valid_result,
    )
    assert reviewer_result.status_code == 200, reviewer_result.text

    outsider_result = client.post(
        f"/visuals/candidates/{candidate_id}/result",
        headers=outsider,
        json=valid_result,
    )
    assert outsider_result.status_code == 403

    producer_decision = client.post(
        f"/visuals/{project_id}/shots/{first_shot['id']}/versions/{first_shot['current_version_id']}/candidates/{candidate_id}/decisions",
        headers=producer,
        json={
            "expected_shot_lock_version": first_shot["lock_version"],
            "decision": "selected",
            "rationale": "A producer cannot approve their own candidate.",
        },
    )
    assert producer_decision.status_code == 403

    reviewer_submit = client.post(
        f"/visuals/{project_id}/submit",
        headers=reviewer,
        json={"expected_project_lock_version": body["project"]["lock_version"]},
    )
    assert reviewer_submit.status_code != 403
