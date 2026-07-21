from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.operator_api.access import OperatorRole
from src.operator_api.access_runtime import install_operator_access
from src.operator_api.auth import OperatorAuthSettings


BRAND_A = "11111111-1111-1111-1111-111111111111"
BRAND_B = "22222222-2222-2222-2222-222222222222"
CONTENT_ID = "33333333-3333-3333-3333-333333333333"
JOB_ID = "44444444-4444-4444-4444-444444444444"


class Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(
        self,
        *,
        artifact_creator: str = "producer.one",
        reference_job_brand: str = BRAND_A,
    ) -> None:
        self.artifact_creator = artifact_creator
        self.reference_job_brand = reference_job_brand

    def execute(self, sql: str, params=()):
        if "SELECT mp.brand_id FROM football_brief.portfolio_content" in sql:
            return Rows([{"brand_id": BRAND_A}])
        if "SELECT stage FROM football_brief.portfolio_content" in sql:
            return Rows([{"stage": "preview"}])
        if "SELECT kind, created_by FROM football_brief.portfolio_content_artifacts" in sql:
            return Rows(
                [
                    {"kind": "voiceover", "created_by": self.artifact_creator},
                    {"kind": "preview", "created_by": self.artifact_creator},
                ]
            )
        if "SELECT id FROM football_brief.brands WHERE slug=" in sql:
            return Rows([{"id": BRAND_A}])
        if "FROM football_brief.reference_ingestion_jobs rij" in sql:
            return Rows([{"brand_id": self.reference_job_brand}])
        return Rows([])


class FakeDatabase:
    def __init__(
        self,
        *,
        artifact_creator: str = "producer.one",
        reference_job_brand: str = BRAND_A,
    ) -> None:
        self.connection_value = FakeConnection(
            artifact_creator=artifact_creator,
            reference_job_brand=reference_job_brand,
        )

    @contextmanager
    def connection(self):
        yield self.connection_value


def app_for(
    *,
    role: OperatorRole,
    operator_id: str,
    artifact_creator: str = "producer.one",
    reference_job_brand: str = BRAND_A,
) -> TestClient:
    app = FastAPI()

    @app.get("/portfolio/queue")
    def queue():
        return {
            "ok": True,
            "count": 2,
            "items": [
                {"id": "a", "brand_id": BRAND_A},
                {"id": "b", "brand_id": BRAND_B},
            ],
        }

    @app.post("/portfolio/plans")
    def create_plan(payload: dict[str, Any]):
        return {"ok": True, "payload": payload}

    @app.post(f"/portfolio/content/{CONTENT_ID}/approvals")
    def approve(payload: dict[str, Any]):
        return {"ok": True, "payload": payload}

    @app.post(f"/portfolio/reference-jobs/{JOB_ID}/progress")
    def progress(payload: dict[str, Any]):
        return {"ok": True, "payload": payload}

    settings = OperatorAuthSettings.for_tests(
        operator_id=operator_id,
        roles=(role,),
        brand_ids=(BRAND_A,),
    )
    install_operator_access(
        app,
        database=FakeDatabase(
            artifact_creator=artifact_creator,
            reference_job_brand=reference_job_brand,
        ),
        auth_settings=settings,
    )
    return TestClient(app)


def test_current_access_exposes_role_and_brand_scope() -> None:
    client = app_for(role=OperatorRole.REVIEWER, operator_id="reviewer.one")
    response = client.get("/access/me", headers={"X-Operator-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["operator"] == {
        "operator_id": "reviewer.one",
        "display_name": "reviewer.one",
        "active": True,
        "roles": ["reviewer"],
        "brand_ids": [BRAND_A],
        "portfolio_wide": False,
    }


def test_reviewer_queue_is_filtered_to_assigned_brand() -> None:
    client = app_for(role=OperatorRole.REVIEWER, operator_id="reviewer.one")
    response = client.get("/portfolio/queue", headers={"X-Operator-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["items"] == [{"id": "a", "brand_id": BRAND_A}]
    assert response.json()["count"] == 1


def test_producer_can_submit_assigned_brand_payload_and_body_survives_middleware() -> None:
    client = app_for(role=OperatorRole.PRODUCER, operator_id="producer.one")
    payload = {"brand_id": BRAND_A, "month_start": "2026-08-01", "target_count": 24}
    response = client.post(
        "/portfolio/plans",
        headers={"X-Operator-Key": "test-key"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["payload"] == payload


def test_producer_is_denied_for_unassigned_brand() -> None:
    client = app_for(role=OperatorRole.PRODUCER, operator_id="producer.one")
    response = client.post(
        "/portfolio/plans",
        headers={"X-Operator-Key": "test-key"},
        json={"brand_id": BRAND_B, "month_start": "2026-08-01", "target_count": 24},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "brand_access_denied"


def test_reference_job_inherits_its_reference_brand_scope() -> None:
    client = app_for(role=OperatorRole.PRODUCER, operator_id="producer.one")
    payload = {"status": "running", "stage": "analysis", "progress_percent": 50}
    response = client.post(
        f"/portfolio/reference-jobs/{JOB_ID}/progress",
        headers={"X-Operator-Key": "test-key"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["payload"] == payload

    denied = app_for(
        role=OperatorRole.PRODUCER,
        operator_id="producer.one",
        reference_job_brand=BRAND_B,
    ).post(
        f"/portfolio/reference-jobs/{JOB_ID}/progress",
        headers={"X-Operator-Key": "test-key"},
        json=payload,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "brand_access_denied"


def test_reviewer_cannot_approve_artifacts_they_created() -> None:
    client = app_for(
        role=OperatorRole.REVIEWER,
        operator_id="reviewer.one",
        artifact_creator="reviewer.one",
    )
    response = client.post(
        f"/portfolio/content/{CONTENT_ID}/approvals",
        headers={"X-Operator-Key": "test-key"},
        json={"gate": "preview", "decision": "approved", "rationale": "reviewed"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "self_review_not_allowed"


def test_independent_reviewer_can_approve_assigned_brand() -> None:
    client = app_for(
        role=OperatorRole.REVIEWER,
        operator_id="reviewer.one",
        artifact_creator="producer.one",
    )
    payload = {"gate": "preview", "decision": "approved", "rationale": "reviewed"}
    response = client.post(
        f"/portfolio/content/{CONTENT_ID}/approvals",
        headers={"X-Operator-Key": "test-key"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["payload"] == payload
