from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p97_delivery_support import p89_database, p97_ready
from tests.integration.test_p97_platform_delivery_lifecycle import (
    delivery_request,
    target_request,
)


pytestmark = pytest.mark.integration


def delivery_client(database, ready) -> TestClient:
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Delivery Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Delivery Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["publisher"]: OperatorIdentity(
            operator_id=str(ready["publisher"]),
            key_name="publisher-key",
            display_name="Delivery Publisher",
            roles=frozenset({OperatorRole.PUBLISHER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["outsider_publisher"]: OperatorIdentity(
            operator_id=str(ready["outsider_publisher"]),
            key_name="outside-publisher-key",
            display_name="Other Brand Publisher",
            roles=frozenset({OperatorRole.PUBLISHER}),
            brand_ids=frozenset({str(ready["brand_two"])}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(ready["admin"]),
            "producer-key": str(ready["producer"]),
            "publisher-key": str(ready["publisher"]),
            "outside-publisher-key": str(ready["outsider_publisher"]),
        },
        identities=identities,
    )
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=OperatorRuntimeSettings(
                _env_file=None,
                database_require_schema=False,
            ),
        )
    )


def test_delivery_api_separates_admin_producer_publisher_and_brand_access(
    p89_database,
    p97_ready,
) -> None:
    client = delivery_client(p89_database, p97_ready)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    publisher = {"X-Operator-Key": "publisher-key"}
    outsider = {"X-Operator-Key": "outside-publisher-key"}

    target_payload = target_request(key="api-simulated-target").model_dump(mode="json")
    assert client.post("/delivery-targets", headers=publisher, json=target_payload).status_code == 403
    created_target = client.post("/delivery-targets", headers=admin, json=target_payload)
    assert created_target.status_code == 200, created_target.text
    target_id = created_target.json()["target"]["id"]
    activated = client.post(f"/delivery-targets/{target_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text
    target = activated.json()["target"]

    payload = delivery_request(
        p97_ready,
        target,
        key="p97-api-delivery-001",
    ).model_dump(mode="json")
    assert client.post("/deliveries", headers=admin, json=payload).status_code == 403
    assert client.post("/deliveries", headers=producer, json=payload).status_code == 403
    assert client.post("/deliveries", headers=outsider, json=payload).status_code == 403
    created = client.post("/deliveries", headers=publisher, json=payload)
    assert created.status_code == 200, created.text
    delivery_id = created.json()["delivery"]["id"]

    assert client.get(f"/deliveries/{delivery_id}", headers=producer).status_code == 403
    assert client.get(f"/deliveries/{delivery_id}", headers=outsider).status_code == 403
    visible = client.get(f"/deliveries/{delivery_id}", headers=publisher)
    assert visible.status_code == 200, visible.text

    claim_payload = {
        "worker_id": p97_ready["publisher"],
        "target_ids": [target_id],
        "lease_seconds": 120,
    }
    assert client.post("/deliveries/claim", headers=producer, json=claim_payload).status_code == 403
    wrong_worker = {**claim_payload, "worker_id": p97_ready["producer"]}
    assert client.post("/deliveries/claim", headers=publisher, json=wrong_worker).status_code == 403
    claimed = client.post("/deliveries/claim", headers=publisher, json=claim_payload)
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()["claimed"]
    assert claim["delivery"]["id"] == delivery_id

    execute_payload = {
        "delivery_request_id": delivery_id,
        "worker_id": p97_ready["publisher"],
        "lease_token": claim["lease_token"],
    }
    assert client.post(
        f"/deliveries/{delivery_id}/execute",
        headers=producer,
        json=execute_payload,
    ).status_code == 403
    executed = client.post(
        f"/deliveries/{delivery_id}/execute",
        headers=publisher,
        json=execute_payload,
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["delivery"]["status"] == "succeeded"

    reconciled = client.post(
        f"/deliveries/{delivery_id}/reconcile",
        headers=publisher,
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["reconciliation"]["platform_status"] == "published"
    assert client.post(
        f"/deliveries/{delivery_id}/reconcile",
        headers=outsider,
    ).status_code == 403

    listed = client.get("/deliveries", headers=publisher)
    assert listed.status_code == 200, listed.text
    assert {item["id"] for item in listed.json()["items"]} == {delivery_id}
    outside_list = client.get("/deliveries", headers=outsider)
    assert outside_list.status_code == 200, outside_list.text
    assert outside_list.json()["items"] == []
