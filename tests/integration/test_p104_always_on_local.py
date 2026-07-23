from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.production_workflow_service import ProductionWorkflowService
from src.domain.production_workflow import ReviewDecision
from src.infrastructure.database.connection import Database
from src.operations.local_pipeline import LocalPipelineService
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded

__all__ = ["database", "seeded"]
pytestmark = pytest.mark.integration


def test_bounded_script_batch_is_durable_zero_cost_and_idempotent(
    database: Database,
    seeded: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = ProductionWorkflowService(database)
    created = workflow.initialize(content_id=seeded["content_id"], actor=seeded["producer"])
    submitted = workflow.submit(
        workflow_id=created["workflow_id"],
        expected_lock_version=1,
        actor=seeded["producer"],
    )
    approved = workflow.decide(
        workflow_id=created["workflow_id"],
        expected_lock_version=submitted["workflow"]["lock_version"],
        reviewer=seeded["reviewer"],
        decision=ReviewDecision.APPROVED,
        rationale="Concept is approved for bounded local script generation",
    )
    assert approved["workflow"]["current_stage"] == "script_draft"

    monkeypatch.setenv("LOCAL_PRODUCER_OPERATOR_ID", str(seeded["producer"]))
    pipeline = LocalPipelineService(database)
    first = pipeline.enqueue_scripts(
        limit=5,
        actor=str(seeded["producer"]),
        brand_ids=[seeded["brand_id"]],
    )
    assert first["ok"] is True
    assert len(first["enqueued"]) == 1
    assert first["enqueued"][0]["reused"] is False

    replay = pipeline.enqueue_scripts(
        limit=5,
        actor=str(seeded["producer"]),
        brand_ids=[seeded["brand_id"]],
    )
    assert len(replay["enqueued"]) == 1
    assert replay["enqueued"][0]["reused"] is True
    assert replay["enqueued"][0]["id"] == first["enqueued"][0]["id"]

    with database.connection() as conn:
        row = conn.execute(
            """SELECT job_type,status,provider,preferred_worker_id,
                      estimated_cost_usd,reserved_cost_usd,input_payload,legacy_source
               FROM football_brief.generation_jobs WHERE id=%s""",
            (first["enqueued"][0]["id"],),
        ).fetchone()
    assert row["job_type"] == "script"
    assert row["status"] == "queued"
    assert row["provider"] == "ollama-local"
    assert row["preferred_worker_id"] == seeded["producer"]
    assert row["estimated_cost_usd"] == Decimal("0.000000")
    assert row["reserved_cost_usd"] == Decimal("0.000000")
    assert row["input_payload"]["request"]["adapter_mode"] == "local_model"
    assert row["legacy_source"]["bounded_batch"] is True

    status = pipeline.status(brand_ids=[seeded["brand_id"]])
    assert status["eligible"]["scripts"] == 1
    assert any(
        item["job_type"] == "script" and item["status"] == "queued" and item["count"] == 1
        for item in status["jobs"]
    )
    assert status["capabilities"]["managed_renderer"] is False
    assert status["capabilities"]["automatic_approval"] is False
    assert status["capabilities"]["live_publishing"] is False
