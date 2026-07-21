from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.p94_routing_support import p94_ready


pytestmark = pytest.mark.integration


def routing_client(database, ready) -> TestClient:
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


def policy_payload(ready) -> dict:
    return {
        "brand_id": str(ready["brand_one"]),
        "month_start": date(2026, 10, 1).isoformat(),
        "currency": "USD",
        "monthly_soft_limit": "3",
        "monthly_hard_limit": "10",
        "default_content_limit": "6",
        "approval_threshold": "1",
        "require_approval_for_managed": True,
    }


def plan_payload(ready, policy_id) -> dict:
    shots = []
    for index, shot in enumerate(ready["visual_shots"]):
        if index == 0:
            shots.append(
                {
                    "visual_shot_id": str(shot["id"]),
                    "renderer_preflight_id": str(ready["preflights"][str(shot["id"])]["id"]),
                    "hero_importance": "90",
                    "realism_requirement": "85",
                    "motion_complexity": "80",
                    "continuity_requirement": "90",
                    "factual_control_requirement": "40",
                    "local_preview_quality": "45",
                    "engagement_contribution": "90",
                    "forced_route": "managed_render",
                    "override_rationale": "API test routes the hero shot through managed rendering.",
                }
            )
        else:
            shots.append(
                {
                    "visual_shot_id": str(shot["id"]),
                    "hero_importance": "20",
                    "realism_requirement": "40",
                    "motion_complexity": "35",
                    "continuity_requirement": "70",
                    "factual_control_requirement": "90",
                    "local_preview_quality": "90",
                    "engagement_contribution": "35",
                    "forced_route": "deterministic_animation",
                    "override_rationale": "API test keeps supporting factual shots deterministic.",
                }
            )
    return {
        "budget_policy_id": str(policy_id),
        "shots": shots,
        "recommendation_context": {"source": "p94-api-test"},
    }


def test_routing_api_enforces_roles_brand_scope_and_approval_sequence(
    p89_database,
    p94_ready,
) -> None:
    client = routing_client(p89_database, p94_ready)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}

    assert client.post("/routing/policies", headers=producer, json=policy_payload(p94_ready)).status_code == 403
    created = client.post("/routing/policies", headers=admin, json=policy_payload(p94_ready))
    assert created.status_code == 200, created.text
    policy_id = created.json()["policy"]["id"]
    assert client.post(f"/routing/policies/{policy_id}/activate", headers=reviewer).status_code == 403
    activated = client.post(f"/routing/policies/{policy_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text

    payload = plan_payload(p94_ready, policy_id)
    assert client.post(
        f"/routing/content/{p94_ready['content_one']}/plans",
        headers=reviewer,
        json=payload,
    ).status_code == 403
    assert client.post(
        f"/routing/content/{p94_ready['content_one']}/plans",
        headers=outsider,
        json=payload,
    ).status_code == 403

    draft_response = client.post(
        f"/routing/content/{p94_ready['content_one']}/plans",
        headers=producer,
        json=payload,
    )
    assert draft_response.status_code == 200, draft_response.text
    draft = draft_response.json()
    plan_id = draft["plan"]["id"]
    managed = next(item for item in draft["items"] if item["route"] == "managed_render")

    assert client.get(f"/routing/plans/{plan_id}", headers=outsider).status_code == 403
    assert client.get(f"/routing/plans/{plan_id}", headers=reviewer).status_code == 200
    current = client.get(
        f"/routing/content/{p94_ready['content_one']}/current",
        headers=reviewer,
    )
    assert current.status_code == 200, current.text
    assert current.json()["plan"]["id"] == plan_id

    submitted_response = client.post(
        f"/routing/plans/{plan_id}/submit",
        headers=producer,
        json={"expected_lock_version": draft["plan"]["lock_version"]},
    )
    assert submitted_response.status_code == 200, submitted_response.text
    submitted = submitted_response.json()

    producer_decision = client.post(
        f"/routing/plans/{plan_id}/decisions",
        headers=producer,
        json={
            "expected_lock_version": submitted["plan"]["lock_version"],
            "decision": "approved",
            "approved_ceiling": "3",
            "rationale": "Producer cannot approve their own managed spend.",
        },
    )
    assert producer_decision.status_code == 403

    approved_response = client.post(
        f"/routing/plans/{plan_id}/decisions",
        headers=reviewer,
        json={
            "expected_lock_version": submitted["plan"]["lock_version"],
            "decision": "approved",
            "approved_ceiling": "3",
            "rationale": "Reviewer approves one managed hero shot with a three-dollar ceiling.",
        },
    )
    assert approved_response.status_code == 200, approved_response.text
    approved = approved_response.json()
    assert approved["plan"]["status"] == "approved"

    reviewer_enqueue = client.post(
        f"/routing/plans/{plan_id}/managed-jobs",
        headers=reviewer,
        json={"routing_item_id": managed["id"]},
    )
    assert reviewer_enqueue.status_code == 403

    enqueued = client.post(
        f"/routing/plans/{plan_id}/managed-jobs",
        headers=producer,
        json={
            "routing_item_id": managed["id"],
            "preferred_worker_id": p94_ready["producer"],
            "max_attempts": 1,
        },
    )
    assert enqueued.status_code == 200, enqueued.text
    result = enqueued.json()
    assert result["reservation"]["status"] == "reserved"
    assert Decimal(str(result["reservation"]["reserved_amount"])) == Decimal("2.000000")
    assert result["job"]["provider"] == p94_ready["renderer_entry"]["provider_key"]
    assert result["job"]["input_payload"]["spend_reservation_id"] == result["reservation"]["id"]
