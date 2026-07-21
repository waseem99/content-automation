from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID

import pytest

from src.application.generation_jobs.legacy_adapter import import_legacy_records
from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobEnqueue,
    GenerationJobFailure,
    GenerationJobType,
    LegacyGenerationRecord,
)
from src.application.generation_jobs.service import GenerationJobError, GenerationJobService
from src.infrastructure.database.connection import Database
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded


__all__ = ["database", "seeded"]
pytestmark = pytest.mark.integration


def enqueue_request(
    seeded: dict[str, object],
    *,
    key: str,
    job_type: GenerationJobType = GenerationJobType.KEYFRAME,
    payload: dict | None = None,
    max_attempts: int = 3,
    dependencies: tuple[UUID, ...] = (),
) -> GenerationJobEnqueue:
    return GenerationJobEnqueue(
        portfolio_content_id=seeded["content_id"],
        content_version=1,
        job_type=job_type,
        provider="p68-local" if job_type != GenerationJobType.PUBLISHING else "facebook",
        model_id="preview-v1",
        idempotency_key=key,
        input_payload=payload or {"prompt": key},
        max_attempts=max_attempts,
        estimated_cost_usd=Decimal("0.10"),
        reserved_cost_usd=Decimal("0.10"),
        dependency_job_ids=dependencies,
    )


def claim_one(
    service: GenerationJobService,
    seeded: dict[str, object],
    *,
    worker: str,
    job_types: tuple[GenerationJobType, ...] = (GenerationJobType.KEYFRAME,),
):
    return service.claim(
        worker_id=worker,
        allowed_brand_ids=[seeded["brand_id"]],
        allowed_job_types=job_types,
        requested_job_types=job_types,
        providers=(),
        lease_seconds=120,
    )


def test_idempotency_and_two_competing_workers_create_only_one_claim(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    request = enqueue_request(seeded, key="p87:idempotency:competing-workers")
    first = service.enqueue(request, actor=str(seeded["producer"]))
    reused = service.enqueue(request, actor=str(seeded["producer"]))
    assert reused["reused"] is True
    assert reused["id"] == first["id"]

    conflicting = enqueue_request(
        seeded,
        key="p87:idempotency:competing-workers",
        payload={"prompt": "different immutable input"},
    )
    with pytest.raises(GenerationJobError) as conflict:
        service.enqueue(conflicting, actor=str(seeded["producer"]))
    assert conflict.value.code == "idempotency_conflict"

    workers = (str(seeded["producer"]), str(seeded["admin"]))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda worker: claim_one(
                    GenerationJobService(database),
                    seeded,
                    worker=worker,
                ),
                workers,
            )
        )
    claims = [result for result in results if result is not None]
    assert len(claims) == 1
    assert claims[0]["job"]["id"] == first["id"]
    detail = service.detail(job_id=first["id"])
    assert detail["job"]["status"] == "running"
    assert detail["job"]["attempt_count"] == 1
    assert len(detail["attempts"]) == 1


def test_cancelled_running_job_rejects_late_success(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    job = service.enqueue(
        enqueue_request(seeded, key="p87:cancellation:late-success"),
        actor=str(seeded["producer"]),
    )
    claim = claim_one(service, seeded, worker=str(seeded["producer"]))
    assert claim is not None

    cancelled = service.cancel(
        job_id=job["id"],
        actor=str(seeded["admin"]),
        reason="Operator stopped the obsolete generation request",
    )
    assert cancelled["job"]["status"] == "cancelled"

    with pytest.raises(GenerationJobError) as denied:
        service.complete(
            GenerationJobCompletion(
                job_id=job["id"],
                attempt_id=claim["attempt"]["id"],
                lease_token=claim["lease_token"],
                worker_id=str(seeded["producer"]),
                output_payload={"asset_id": "must-not-register"},
            )
        )
    assert denied.value.code == "generation_job_not_running"
    detail = service.detail(job_id=job["id"])
    assert detail["job"]["output_payload"] is None
    assert detail["attempts"][0]["status"] == "cancelled"


def test_bounded_retries_retain_every_attempt_and_end_in_dead_letter(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    job = service.enqueue(
        enqueue_request(
            seeded,
            key="p87:retry:retained-attempts",
            max_attempts=2,
        ),
        actor=str(seeded["producer"]),
    )
    first = claim_one(service, seeded, worker=str(seeded["producer"]))
    failed = service.fail(
        GenerationJobFailure(
            job_id=job["id"],
            attempt_id=first["attempt"]["id"],
            lease_token=first["lease_token"],
            worker_id=str(seeded["producer"]),
            error_code="temporary_gpu_oom",
            error_message="GPU allocation failed temporarily",
            retryable=True,
            actual_cost_usd=Decimal("0.01"),
        )
    )
    assert failed["job"]["status"] == "failed"
    service.retry(job_id=job["id"], actor=str(seeded["admin"]))

    second = claim_one(service, seeded, worker=str(seeded["producer"]))
    dead = service.fail(
        GenerationJobFailure(
            job_id=job["id"],
            attempt_id=second["attempt"]["id"],
            lease_token=second["lease_token"],
            worker_id=str(seeded["producer"]),
            error_code="temporary_gpu_oom",
            error_message="GPU allocation failed again",
            retryable=True,
            actual_cost_usd=Decimal("0.02"),
        )
    )
    assert dead["dead_lettered"] is True
    assert dead["job"]["status"] == "dead_letter"

    detail = service.detail(job_id=job["id"])
    assert [attempt["attempt_number"] for attempt in detail["attempts"]] == [1, 2]
    assert [attempt["status"] for attempt in detail["attempts"]] == ["failed", "failed"]
    assert detail["job"]["actual_cost_usd"] == Decimal("0.030000")
    with pytest.raises(GenerationJobError) as retry_denied:
        service.retry(job_id=job["id"], actor=str(seeded["admin"]))
    assert retry_denied.value.code == "generation_job_not_retryable"


def test_expired_lease_is_recovered_after_restart_and_reclaimed(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    job = service.enqueue(
        enqueue_request(seeded, key="p87:recovery:expired-lease", max_attempts=2),
        actor=str(seeded["producer"]),
    )
    first = claim_one(service, seeded, worker=str(seeded["producer"]))
    with database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.generation_job_attempts
               SET heartbeat_at=now()-interval '10 minutes',
                   lease_expires_at=now()-interval '5 minutes'
               WHERE id=%s""",
            (first["attempt"]["id"],),
        )
        conn.execute(
            """UPDATE football_brief.generation_jobs
               SET heartbeat_at=now()-interval '10 minutes',
                   lease_expires_at=now()-interval '5 minutes'
               WHERE id=%s""",
            (job["id"],),
        )

    recovered = service.recover_stale(actor=str(seeded["admin"]))
    assert recovered["recovered"] == 1
    detail = service.detail(job_id=job["id"])
    assert detail["job"]["status"] == "queued"
    assert detail["attempts"][0]["status"] == "timed_out"

    second = claim_one(service, seeded, worker=str(seeded["producer"]))
    assert second is not None
    assert second["attempt"]["attempt_number"] == 2
    completed = service.complete(
        GenerationJobCompletion(
            job_id=job["id"],
            attempt_id=second["attempt"]["id"],
            lease_token=second["lease_token"],
            worker_id=str(seeded["producer"]),
            output_payload={"asset_id": "recovered-output"},
        )
    )
    assert completed["job"]["status"] == "succeeded"


def test_dependencies_block_claim_until_parent_succeeds(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    parent = service.enqueue(
        enqueue_request(seeded, key="p87:dependency:parent"),
        actor=str(seeded["producer"]),
    )
    child = service.enqueue(
        enqueue_request(
            seeded,
            key="p87:dependency:child",
            dependencies=(parent["id"],),
        ),
        actor=str(seeded["producer"]),
    )

    first = claim_one(service, seeded, worker=str(seeded["producer"]))
    assert first["job"]["id"] == parent["id"]
    service.complete(
        GenerationJobCompletion(
            job_id=parent["id"],
            attempt_id=first["attempt"]["id"],
            lease_token=first["lease_token"],
            worker_id=str(seeded["producer"]),
            output_payload={"asset_id": "parent-output"},
        )
    )
    second = claim_one(service, seeded, worker=str(seeded["producer"]))
    assert second["job"]["id"] == child["id"]


def test_queued_old_content_version_is_dead_lettered_before_claim(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    job = service.enqueue(
        enqueue_request(seeded, key="p87:content-version:superseded"),
        actor=str(seeded["producer"]),
    )
    with database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.portfolio_content
               SET version=version+1 WHERE id=%s""",
            (seeded["content_id"],),
        )
    recovered = service.recover_stale(actor=str(seeded["admin"]))
    assert recovered["content_version_superseded"] == 1
    detail = service.detail(job_id=job["id"])
    assert detail["job"]["status"] == "dead_letter"
    assert detail["job"]["error_code"] == "content_version_superseded"
    assert claim_one(service, seeded, worker=str(seeded["producer"])) is None


def test_legacy_terminal_and_interrupted_records_import_idempotently(
    database: Database, seeded: dict[str, object]
) -> None:
    service = GenerationJobService(database)
    records = [
        LegacyGenerationRecord(
            legacy_id="p68-done-1",
            status="succeeded",
            job_type=GenerationJobType.KEYFRAME,
            provider="p68-local",
            worker_id="p68.local.worker",
            input_payload={"prompt": "completed"},
            output_payload={"path": "D:/p68/frames/done-1.png", "sha256": "a" * 64},
            attempt_count=2,
        ),
        LegacyGenerationRecord(
            legacy_id="p68-running-1",
            status="running",
            job_type=GenerationJobType.KEYFRAME,
            provider="p68-local",
            worker_id="p68.local.worker",
            input_payload={"prompt": "interrupted"},
            attempt_count=1,
        ),
    ]
    result = import_legacy_records(
        service=service,
        records=records,
        content_id=seeded["content_id"],
        content_version=1,
        actor=str(seeded["admin"]),
        source_name="p68-test-ledger",
    )
    assert result["imported"] == 2
    assert result["recovered_to_queue"] == 1

    repeated = import_legacy_records(
        service=service,
        records=records,
        content_id=seeded["content_id"],
        content_version=1,
        actor=str(seeded["admin"]),
        source_name="p68-test-ledger",
    )
    assert repeated["reused"] == 2

    details = [service.detail(job_id=UUID(job_id)) for job_id in result["job_ids"]]
    statuses = sorted(detail["job"]["status"] for detail in details)
    assert statuses == ["queued", "succeeded"]
    succeeded = next(detail for detail in details if detail["job"]["status"] == "succeeded")
    assert len(succeeded["attempts"]) == 2
    assert [attempt["status"] for attempt in succeeded["attempts"]] == ["abandoned", "succeeded"]
