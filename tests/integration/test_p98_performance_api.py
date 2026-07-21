from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p98_performance_support import p89_database, p98_ready
from tests.integration.test_p98_performance_lifecycle import (
    experiment_request,
    import_request,
)


pytestmark = pytest.mark.integration


def performance_client(database, ready) -> TestClient:
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Analytics Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Analytics Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Analytics Reviewer",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
        ready["outsider_publisher"]: OperatorIdentity(
            operator_id=str(ready["outsider_publisher"]),
            key_name="outside-key",
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
            "reviewer-key": str(ready["reviewer"]),
            "outside-key": str(ready["outsider_publisher"]),
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


def test_performance_api_separates_import_read_review_and_brand_scope(
    p89_database,
    p98_ready,
) -> None:
    client = performance_client(p89_database, p98_ready)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outside-key"}
    observed_at = datetime.now(timezone.utc)

    early_request = import_request(
        p98_ready,
        key="p98-api-early",
        observed_at=observed_at,
        suffix="early",
        a_views=700,
        b_views=600,
    )
    assert client.post(
        "/performance/imports",
        headers=producer,
        json=early_request.model_dump(mode="json"),
    ).status_code == 403
    early = client.post(
        "/performance/imports",
        headers=admin,
        json=early_request.model_dump(mode="json"),
    )
    assert early.status_code == 200, early.text

    late_request = import_request(
        p98_ready,
        key="p98-api-late",
        observed_at=observed_at + timedelta(hours=24),
        suffix="late",
        a_views=3200,
        b_views=1600,
    )
    late = client.post(
        "/performance/imports",
        headers=admin,
        json=late_request.model_dump(mode="json"),
    )
    assert late.status_code == 200, late.text

    visible = client.get("/performance/observations?latest_per_delivery=true", headers=producer)
    assert visible.status_code == 200, visible.text
    assert len(visible.json()["items"]) == 2
    dashboard = client.get(
        f"/performance/dashboard/{p98_ready['brand_one']}?minimum_items=2&minimum_normalized_views=1000",
        headers=producer,
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["data_status"] == "meaningful"
    assert client.get(
        f"/performance/dashboard/{p98_ready['brand_one']}",
        headers=outsider,
    ).status_code == 403

    experiment_payload = experiment_request(
        p98_ready,
        key="p98-api-experiment",
    ).model_dump(mode="json")
    assert client.post(
        "/performance/experiments",
        headers=producer,
        json=experiment_payload,
    ).status_code == 403
    created = client.post(
        "/performance/experiments",
        headers=admin,
        json=experiment_payload,
    )
    assert created.status_code == 200, created.text
    experiment_id = created.json()["experiment"]["id"]
    activated = client.post(
        f"/performance/experiments/{experiment_id}/activate",
        headers=admin,
    )
    assert activated.status_code == 200, activated.text
    assert client.post(
        f"/performance/experiments/{experiment_id}/evaluate",
        headers=producer,
        json={"rationale": "Producer cannot evaluate controlled evidence."},
    ).status_code == 403
    evaluated = client.post(
        f"/performance/experiments/{experiment_id}/evaluate",
        headers=reviewer,
        json={"rationale": "Both variants meet the declared thresholds; variant A leads materially."},
    )
    assert evaluated.status_code == 200, evaluated.text
    evaluation = evaluated.json()["evaluation"]
    assert evaluation["result_status"] == "meaningful_result"

    observation_ids = [
        item["id"]
        for response in (early.json(), late.json())
        for item in response["observations"]
    ]
    recommendation = client.post(
        "/performance/recommendations",
        headers=reviewer,
        json={
            "brand_id": str(p98_ready["brand_one"]),
            "experiment_result_id": evaluation["id"],
            "recommendation_key": "api-prefer-direct-hook",
            "recommendation": (
                "Use the direct factual hook as an advisory input for the next human-reviewed concept."
            ),
            "cited_observation_ids": observation_ids,
            "metric_citations": [
                {
                    "metric": "normalized_views",
                    "variant_a": 2880,
                    "variant_b": 1440,
                }
            ],
            "confidence": "high",
        },
    )
    assert recommendation.status_code == 200, recommendation.text
    assert recommendation.json()["recommendation"]["advisory_only"] is True
