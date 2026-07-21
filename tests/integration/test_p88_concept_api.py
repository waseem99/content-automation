from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p88_concept_support import p88_database, p88_seeded


pytestmark = pytest.mark.integration


def concept_client(database, seeded) -> TestClient:
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


def generation_payload(brand_id) -> dict:
    return {
        "brand_id": str(brand_id),
        "month_start": "2026-09-01",
        "candidate_count": 4,
        "format_mix": {"vertical_short": 2, "carousel": 2},
        "pillar_targets": {"education": 2, "conservation": 2},
        "seed": 55,
        "adapter_mode": "deterministic",
    }


def test_concept_api_enforces_roles_brand_scope_and_admin_only_application(
    p88_database, p88_seeded
) -> None:
    client = concept_client(p88_database, p88_seeded)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    admin = {"X-Operator-Key": "admin-key"}

    denied_reviewer_generation = client.post(
        "/concepts/batches",
        headers=reviewer,
        json=generation_payload(p88_seeded["brand_one"]),
    )
    assert denied_reviewer_generation.status_code == 403

    denied_outsider_generation = client.post(
        "/concepts/batches",
        headers=outsider,
        json=generation_payload(p88_seeded["brand_one"]),
    )
    assert denied_outsider_generation.status_code == 403

    generated = client.post(
        "/concepts/batches",
        headers=producer,
        json=generation_payload(p88_seeded["brand_one"]),
    )
    assert generated.status_code == 200, generated.text
    batch = generated.json()["batch"]
    candidates = generated.json()["candidates"]
    assert len(candidates) == 4

    producer_list = client.get("/concepts/batches", headers=producer)
    outsider_list = client.get("/concepts/batches", headers=outsider)
    assert producer_list.status_code == 200
    assert producer_list.json()["count"] == 1
    assert outsider_list.status_code == 200
    assert outsider_list.json()["count"] == 0

    producer_review = client.post(
        f"/concepts/candidates/{candidates[0]['id']}/review",
        headers=producer,
        json={"action": "shortlist", "rationale": "Producer cannot approve candidates."},
    )
    assert producer_review.status_code == 403

    for candidate in candidates:
        reviewed = client.post(
            f"/concepts/candidates/{candidate['id']}/review",
            headers=reviewer,
            json={
                "action": "shortlist",
                "rationale": "Candidate is original, feasible, and aligned with the monthly target.",
            },
        )
        assert reviewed.status_code == 200, reviewed.text

    slate = client.post(
        "/concepts/slates",
        headers=reviewer,
        json={
            "batch_id": batch["id"],
            "selected_count": 4,
            "format_mix": {"vertical_short": 2, "carousel": 2},
            "pillar_targets": {"education": 2, "conservation": 2},
        },
    )
    assert slate.status_code == 200, slate.text
    slate_payload = slate.json()
    slate_id = slate_payload["slate"]["id"]

    approved = client.post(f"/concepts/slates/{slate_id}/approve", headers=reviewer)
    assert approved.status_code == 200, approved.text
    assert approved.json()["slate"]["status"] == "approved"

    schedule = {
        "plan_id": str(p88_seeded["plan_one"]),
        "items": [
            {
                "candidate_id": row["candidate_id"],
                "scheduled_for": date(2026, 9, index).isoformat(),
            }
            for index, row in enumerate(approved.json()["items"], start=1)
        ],
    }
    reviewer_apply = client.post(
        f"/concepts/slates/{slate_id}/apply",
        headers=reviewer,
        json=schedule,
    )
    assert reviewer_apply.status_code == 403
    assert reviewer_apply.json()["detail"] == "admin_required"

    admin_apply = client.post(
        f"/concepts/slates/{slate_id}/apply",
        headers=admin,
        json=schedule,
    )
    assert admin_apply.status_code == 200, admin_apply.text
    assert admin_apply.json()["created_count"] == 4

    detail = client.get(f"/concepts/slates/{slate_id}", headers=reviewer)
    assert detail.status_code == 200
    assert detail.json()["slate"]["status"] == "applied"
