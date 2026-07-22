from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest

from src.application.generation_jobs.models import GenerationJobCompletion
from src.operations import (
    BackupSetRequest,
    DrillCompleteRequest,
    DrillStartRequest,
    MonitorThresholds,
    OperationsEnvironment,
    OperationsReleaseStatus,
    OperationsService,
    ReleaseRecordRequest,
    RestoreEvidenceRequest,
)
from src.operations.job_logging import ObservedGenerationJobService
from tests.integration.test_p87_generation_jobs import (
    claim_one,
    database,
    enqueue_request,
    seeded,
)


__all__ = ["database", "seeded"]
pytestmark = pytest.mark.integration


def release_request(*, key: str, git_char: str, previous_release_id=None) -> ReleaseRecordRequest:
    return ReleaseRecordRequest(
        environment="staging",
        release_key=key,
        git_sha=git_char * 40,
        image_digest="sha256:" + git_char * 64,
        configuration_digest=("f" if git_char != "f" else "e") * 64,
        migration_head="0082_production_operations_integrity.sql",
        previous_release_id=previous_release_id,
    )


def test_release_rollback_and_operational_evidence_are_immutable(database, seeded) -> None:
    service = OperationsService(database)
    admin = str(seeded["admin"])
    first = service.record_release(
        release_request(key="staging-release-0001", git_char="1"),
        actor=admin,
    )["release"]
    service.transition_release(
        release_id=first["id"],
        status=OperationsReleaseStatus.DEPLOYING,
        actor=admin,
    )
    first = service.transition_release(
        release_id=first["id"],
        status=OperationsReleaseStatus.HEALTHY,
        actor=admin,
    )["release"]

    second = service.record_release(
        release_request(
            key="staging-release-0002",
            git_char="2",
            previous_release_id=first["id"],
        ),
        actor=admin,
    )["release"]
    service.transition_release(
        release_id=second["id"],
        status=OperationsReleaseStatus.DEPLOYING,
        actor=admin,
    )
    service.transition_release(
        release_id=second["id"],
        status=OperationsReleaseStatus.FAILED,
        actor=admin,
    )
    rolled_back = service.transition_release(
        release_id=second["id"],
        status=OperationsReleaseStatus.ROLLED_BACK,
        actor=admin,
    )["release"]
    assert rolled_back["status"] == "rolled_back"
    assert rolled_back["previous_release_id"] == first["id"]

    drill = service.start_drill(
        DrillStartRequest(
            environment="staging",
            drill_kind="release_rollback",
            release_id=second["id"],
        ),
        actor=admin,
    )["drill"]
    completed = service.complete_drill(
        drill_id=drill["id"],
        request=DrillCompleteRequest(
            status="passed",
            evidence={
                "failed_release_id": str(second["id"]),
                "restored_release_id": str(first["id"]),
                "readiness_verified": True,
            },
        ),
        actor=admin,
    )["drill"]
    assert completed["status"] == "passed"
    assert completed["evidence_digest"]

    with pytest.raises(psycopg.Error, match="immutable"):
        with database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.operations_releases SET git_sha=%s WHERE id=%s",
                ("9" * 40, first["id"]),
            )


def test_backup_restore_registration_and_drill_evidence(database, seeded) -> None:
    service = OperationsService(database)
    admin = str(seeded["admin"])
    request = BackupSetRequest(
        environment="staging",
        backup_key="staging-backup-0001",
        database_object_ref="object:backups/database-0001.dump",
        artifact_object_ref="object:backups/artifacts-0001.zip",
        database_sha256="a" * 64,
        artifact_sha256="b" * 64,
        migration_head="0082_production_operations_integrity.sql",
        database_bytes=1024,
        artifact_bytes=512,
        retention_until=datetime.now(timezone.utc) + timedelta(days=14),
    )
    backup = service.register_backup(request, actor=admin)
    reused = service.register_backup(request, actor=admin)
    assert backup["reused"] is False
    assert reused["reused"] is True
    assert reused["backup_set"]["id"] == backup["backup_set"]["id"]

    drill = service.start_drill(
        DrillStartRequest(
            environment="staging",
            drill_kind="database_restore",
            backup_set_id=backup["backup_set"]["id"],
        ),
        actor=admin,
    )["drill"]
    restored = service.record_restore(
        RestoreEvidenceRequest(
            backup_set_id=backup["backup_set"]["id"],
            environment="staging",
            database_restored=True,
            artifacts_restored=True,
            migration_head_verified=True,
            database_sha256_verified=True,
            artifact_sha256_verified=True,
            verification={
                "database_row_count_verified": True,
                "media_object_sha256_verified": True,
            },
        ),
        actor=admin,
    )["restore_event"]
    assert restored["database_restored"] is True
    service.complete_drill(
        drill_id=drill["id"],
        request=DrillCompleteRequest(
            status="passed",
            evidence={
                "restore_event_id": str(restored["id"]),
                "database_and_media_verified": True,
            },
        ),
        actor=admin,
    )
    with database.connection() as conn:
        status = conn.execute(
            "SELECT status FROM football_brief.operations_backup_sets WHERE id=%s",
            (backup["backup_set"]["id"],),
        ).fetchone()["status"]
    assert status == "restored"

    with pytest.raises(psycopg.Error, match="immutable"):
        with database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.operations_backup_sets SET database_sha256=%s WHERE id=%s",
                ("c" * 64, backup["backup_set"]["id"]),
            )


def test_monitoring_detects_required_conditions_and_deduplicates(database, seeded) -> None:
    service = OperationsService(database)
    admin = str(seeded["admin"])
    snapshot = {
        "environment": "staging",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "api": {"healthy": False},
        "queue": {
            "ready": 4,
            "running": 1,
            "stalled_ready": 3,
            "expired_leases": 1,
            "dead_letter": 2,
        },
        "jobs": {
            "finished_in_window": 10,
            "failed_in_window": 4,
            "failure_rate": 0.4,
            "average_duration_seconds": 1200,
            "p95_duration_seconds": 1800,
        },
        "storage": {
            "capacity_bytes": 1000,
            "used_bytes": 950,
            "free_bytes": 50,
            "free_ratio": 0.05,
            "missing_objects": 1,
            "quarantined_objects": 1,
        },
        "budgets": [
            {
                "policy_id": "00000000-0000-4000-8000-000000000001",
                "brand_id": str(seeded["brand_id"]),
                "consumed": Decimal("100"),
                "soft_limit": Decimal("80"),
                "hard_limit": Decimal("100"),
                "hard_limit_ratio": Decimal("1"),
            }
        ],
        "backup": {
            "latest_backup_set_id": None,
            "latest_created_at": None,
            "age_seconds": None,
        },
        "thresholds": MonitorThresholds().model_dump(mode="json"),
    }
    first = service.detect_alerts(
        environment=OperationsEnvironment.STAGING,
        snapshot=snapshot,
        actor=admin,
    )
    second = service.detect_alerts(
        environment=OperationsEnvironment.STAGING,
        snapshot=snapshot,
        actor=admin,
    )
    expected = {
        "api_unhealthy",
        "queue_stalled",
        "worker_failed",
        "storage_low",
        "budget_threshold",
        "backup_stale",
    }
    assert {item["alert_kind"] for item in first} == expected
    assert {item["id"] for item in first} == {item["id"] for item in second}

    acknowledged = service.acknowledge_alert(alert_id=first[0]["id"], actor=admin)["alert"]
    assert acknowledged["status"] == "acknowledged"
    resolved = service.resolve_alert(alert_id=first[0]["id"], actor=admin)["alert"]
    assert resolved["status"] == "resolved"


def test_worker_restart_recovers_claim_once_without_loss_or_duplication(
    database,
    seeded,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="content_automation.worker")
    service = ObservedGenerationJobService(database)
    producer = str(seeded["producer"])
    admin = str(seeded["admin"])
    job = service.enqueue(
        enqueue_request(
            seeded,
            key="p99:worker-restart:no-duplicate",
            max_attempts=2,
        ),
        actor=producer,
    )
    first = claim_one(service, seeded, worker=producer)
    assert first is not None
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

    recovered = service.recover_stale(actor=admin)
    assert recovered["recovered"] == 1
    second = claim_one(service, seeded, worker=producer)
    assert second is not None
    assert second["attempt"]["attempt_number"] == 2
    completed = service.complete(
        GenerationJobCompletion(
            job_id=job["id"],
            attempt_id=second["attempt"]["id"],
            lease_token=second["lease_token"],
            worker_id=producer,
            output_payload={"asset_id": "p99-restart-output"},
        )
    )
    assert completed["job"]["status"] == "succeeded"

    detail = service.detail(job_id=job["id"])
    assert detail["job"]["attempt_count"] == 2
    assert [item["status"] for item in detail["attempts"]] == ["timed_out", "succeeded"]
    assert detail["job"]["output_payload"] == {"asset_id": "p99-restart-output"}
    assert sum(item["event"] == "succeeded" for item in detail["events"]) == 1

    drill_service = OperationsService(database)
    drill = drill_service.start_drill(
        DrillStartRequest(
            environment="staging",
            drill_kind="worker_restart",
        ),
        actor=admin,
    )["drill"]
    drill_service.complete_drill(
        drill_id=drill["id"],
        request=DrillCompleteRequest(
            status="passed",
            evidence={
                "job_id": str(job["id"]),
                "first_attempt_id": str(first["attempt"]["id"]),
                "second_attempt_id": str(second["attempt"]["id"]),
                "attempt_count": 2,
                "successful_outputs": 1,
            },
        ),
        actor=admin,
    )

    worker_logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "content_automation.worker"
    ]
    assert any(
        item["event"] == "generation_job_claimed"
        and str(item["job_id"]) == str(job["id"])
        and item["worker_id"] == producer
        for item in worker_logs
    )
    assert any(
        item["event"] == "generation_job_succeeded"
        and str(item["job_id"]) == str(job["id"])
        for item in worker_logs
    )
