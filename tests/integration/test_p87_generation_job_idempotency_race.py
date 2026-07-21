from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.infrastructure.database.connection import Database
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded


__all__ = ["database", "seeded"]


def test_simultaneous_identical_enqueues_resolve_to_one_job(
    database: Database, seeded: dict[str, object]
) -> None:
    request = GenerationJobEnqueue(
        portfolio_content_id=seeded["content_id"],
        content_version=1,
        job_type=GenerationJobType.KEYFRAME,
        provider="p68-local",
        model_id="preview-v1",
        idempotency_key="p87:race:identical-enqueue",
        input_payload={"prompt": "same immutable request"},
    )

    def enqueue_once() -> dict:
        return GenerationJobService(database).enqueue(
            request,
            actor=str(seeded["producer"]),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: enqueue_once(), range(2)))

    assert len({str(result["id"]) for result in results}) == 1
    assert sorted(bool(result["reused"]) for result in results) == [False, True]

    with database.connection() as conn:
        rows = conn.execute(
            """SELECT id FROM football_brief.generation_jobs
               WHERE idempotency_key='p87:race:identical-enqueue'"""
        ).fetchall()
    assert len(rows) == 1
