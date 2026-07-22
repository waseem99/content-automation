from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from src.infrastructure.database.connection import Database
from src.operations.models import (
    BackupSetRequest,
    DrillCompleteRequest,
    DrillStartRequest,
    MonitorThresholds,
    OperationsAlertKind,
    OperationsAlertSeverity,
    OperationsEnvironment,
    OperationsReleaseStatus,
    ReleaseRecordRequest,
    RestoreEvidenceRequest,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


class OperationsError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(code)


class OperationsService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record_release(self, request: ReleaseRecordRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            existing = conn.execute(
                "SELECT * FROM football_brief.operations_releases WHERE release_key=%s",
                (request.release_key,),
            ).fetchone()
            if existing:
                expected = {
                    "environment": request.environment.value,
                    "git_sha": request.git_sha,
                    "image_digest": request.image_digest,
                    "configuration_digest": request.configuration_digest,
                    "migration_head": request.migration_head,
                    "previous_release_id": request.previous_release_id,
                }
                mismatches = {
                    key: {"expected": str(value), "actual": str(existing[key])}
                    for key, value in expected.items()
                    if str(existing[key]) != str(value)
                }
                if mismatches:
                    raise OperationsError(
                        "operations_release_key_conflict",
                        details={"release_id": str(existing["id"]), "mismatches": mismatches},
                    )
                return {"ok": True, "release": dict(existing), "reused": True}
            release = conn.execute(
                """INSERT INTO football_brief.operations_releases
                   (environment,release_key,git_sha,image_digest,configuration_digest,
                    migration_head,previous_release_id,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.environment.value,
                    request.release_key,
                    request.git_sha,
                    request.image_digest,
                    request.configuration_digest,
                    request.migration_head,
                    request.previous_release_id,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "release": dict(release), "reused": False}

    def transition_release(
        self,
        *,
        release_id: UUID,
        status: OperationsReleaseStatus,
        actor: str,
    ) -> dict[str, Any]:
        timestamp_column = {
            OperationsReleaseStatus.DEPLOYING: "deploying_at",
            OperationsReleaseStatus.HEALTHY: "healthy_at",
            OperationsReleaseStatus.FAILED: "failed_at",
            OperationsReleaseStatus.ROLLED_BACK: "rolled_back_at",
            OperationsReleaseStatus.RETIRED: "retired_at",
        }.get(status)
        if timestamp_column is None:
            raise OperationsError("unsupported_release_transition_target")
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            updated = conn.execute(
                f"""UPDATE football_brief.operations_releases
                    SET status=%s,{timestamp_column}=now()
                    WHERE id=%s RETURNING *""",
                (status.value, release_id),
            ).fetchone()
            if not updated:
                raise OperationsError("operations_release_not_found")
        return {"ok": True, "release": dict(updated)}

    def register_backup(self, request: BackupSetRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            existing = conn.execute(
                "SELECT * FROM football_brief.operations_backup_sets WHERE backup_key=%s",
                (request.backup_key,),
            ).fetchone()
            if existing:
                expected = request.model_dump(mode="python")
                fields = (
                    "environment",
                    "database_object_ref",
                    "artifact_object_ref",
                    "database_sha256",
                    "artifact_sha256",
                    "migration_head",
                    "database_bytes",
                    "artifact_bytes",
                    "retention_until",
                )
                if any(str(existing[field]) != str(expected[field]) for field in fields):
                    raise OperationsError(
                        "operations_backup_key_conflict",
                        details={"backup_set_id": str(existing["id"])},
                    )
                return {"ok": True, "backup_set": dict(existing), "reused": True}
            backup = conn.execute(
                """INSERT INTO football_brief.operations_backup_sets
                   (environment,backup_key,database_object_ref,artifact_object_ref,
                    database_sha256,artifact_sha256,migration_head,database_bytes,
                    artifact_bytes,retention_until,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.environment.value,
                    request.backup_key,
                    request.database_object_ref,
                    request.artifact_object_ref,
                    request.database_sha256,
                    request.artifact_sha256,
                    request.migration_head,
                    request.database_bytes,
                    request.artifact_bytes,
                    request.retention_until,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "backup_set": dict(backup), "reused": False}

    def start_drill(self, request: DrillStartRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            drill = conn.execute(
                """INSERT INTO football_brief.operations_drill_runs
                   (environment,drill_kind,release_id,backup_set_id,started_by)
                   VALUES (%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.environment.value,
                    request.drill_kind.value,
                    request.release_id,
                    request.backup_set_id,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "drill": dict(drill)}

    def complete_drill(
        self,
        *,
        drill_id: UUID,
        request: DrillCompleteRequest,
        actor: str,
    ) -> dict[str, Any]:
        evidence = {
            **request.evidence,
            "completed_by": actor,
            "completed_at": _utcnow().isoformat(),
        }
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            updated = conn.execute(
                """UPDATE football_brief.operations_drill_runs
                   SET status=%s,evidence=%s::jsonb,evidence_digest=%s,completed_at=now()
                   WHERE id=%s AND status='running' RETURNING *""",
                (request.status.value, _json(evidence), _hash(evidence), drill_id),
            ).fetchone()
            if not updated:
                raise OperationsError("operations_drill_not_running")
        return {"ok": request.status.value == "passed", "drill": dict(updated)}

    def record_restore(self, request: RestoreEvidenceRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            event = conn.execute(
                """INSERT INTO football_brief.operations_restore_events
                   (backup_set_id,environment,database_restored,artifacts_restored,
                    migration_head_verified,database_sha256_verified,artifact_sha256_verified,
                    verification,restored_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                (
                    request.backup_set_id,
                    request.environment.value,
                    request.database_restored,
                    request.artifacts_restored,
                    request.migration_head_verified,
                    request.database_sha256_verified,
                    request.artifact_sha256_verified,
                    _json(request.verification),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.operations_backup_sets
                   SET status='restored',restored_at=now()
                   WHERE id=%s AND status='available'""",
                (request.backup_set_id,),
            )
        return {"ok": True, "restore_event": dict(event)}

    def snapshot(
        self,
        *,
        environment: OperationsEnvironment,
        api_healthy: bool,
        storage_capacity_bytes: int,
        thresholds: MonitorThresholds | None = None,
    ) -> dict[str, Any]:
        if storage_capacity_bytes <= 0:
            raise OperationsError("storage_capacity_bytes_must_be_positive")
        limits = thresholds or MonitorThresholds()
        with self.database.connection() as conn:
            queue = conn.execute(
                """SELECT
                       count(*) FILTER (WHERE status='queued' AND available_at<=now()) AS ready,
                       count(*) FILTER (WHERE status='running') AS running,
                       count(*) FILTER (
                           WHERE status='queued' AND available_at<=now()
                             AND queued_at<now()-(%s*interval '1 second')
                       ) AS stalled_ready,
                       count(*) FILTER (
                           WHERE status='running' AND lease_expires_at<now()
                       ) AS expired_leases,
                       count(*) FILTER (WHERE status='dead_letter') AS dead_letter
                   FROM football_brief.generation_jobs""",
                (limits.queue_stall_seconds,),
            ).fetchone()
            attempts = conn.execute(
                """SELECT
                       count(*) FILTER (WHERE finished_at IS NOT NULL) AS finished,
                       count(*) FILTER (WHERE status IN ('failed','superseded') AND finished_at IS NOT NULL) AS failed,
                       COALESCE(avg(extract(epoch FROM (finished_at-started_at)))
                           FILTER (WHERE finished_at IS NOT NULL),0) AS average_duration_seconds,
                       COALESCE(percentile_cont(0.95) WITHIN GROUP (
                           ORDER BY extract(epoch FROM (finished_at-started_at))
                       ) FILTER (WHERE finished_at IS NOT NULL),0) AS p95_duration_seconds
                   FROM football_brief.generation_attempts
                   WHERE started_at>=now()-(%s*interval '1 second')""",
                (limits.failure_window_seconds,),
            ).fetchone()
            storage = conn.execute(
                """SELECT COALESCE(sum(size_bytes) FILTER (WHERE status='available'),0) AS used_bytes,
                          count(*) FILTER (WHERE status='missing') AS missing_objects,
                          count(*) FILTER (WHERE status='quarantined') AS quarantined_objects
                   FROM football_brief.shared_storage_objects sso
                   JOIN football_brief.shared_storage_backends ssb ON ssb.id=sso.backend_id
                   WHERE ssb.environment=%s""",
                (environment.value,),
            ).fetchone()
            budget_rows = conn.execute(
                """SELECT pbp.id,pbp.brand_id,pbp.monthly_soft_limit,pbp.monthly_hard_limit,
                          COALESCE(sum(
                              CASE psr.status
                                WHEN 'reserved' THEN greatest(psr.reserved_amount,psr.actual_amount)
                                WHEN 'reconciled' THEN psr.actual_amount
                                ELSE 0
                              END
                          ),0) AS consumed
                   FROM football_brief.production_budget_policies pbp
                   LEFT JOIN football_brief.shot_routing_plans srp
                     ON srp.budget_policy_id=pbp.id
                   LEFT JOIN football_brief.production_spend_reservations psr
                     ON psr.routing_plan_id=srp.id
                   WHERE pbp.status='active'
                     AND pbp.month_start=date_trunc('month',now())::date
                   GROUP BY pbp.id,pbp.brand_id,pbp.monthly_soft_limit,pbp.monthly_hard_limit"""
            ).fetchall()
            backup = conn.execute(
                """SELECT * FROM football_brief.operations_backup_sets
                   WHERE environment=%s AND status IN ('available','restored')
                   ORDER BY created_at DESC LIMIT 1""",
                (environment.value,),
            ).fetchone()

        finished = int(attempts["finished"])
        failed = int(attempts["failed"])
        failure_rate = failed / finished if finished else 0.0
        used_bytes = int(storage["used_bytes"])
        free_bytes = max(storage_capacity_bytes - used_bytes, 0)
        free_ratio = free_bytes / storage_capacity_bytes
        budgets = [
            {
                "policy_id": str(row["id"]),
                "brand_id": str(row["brand_id"]),
                "consumed": _decimal(row["consumed"]),
                "soft_limit": _decimal(row["monthly_soft_limit"]),
                "hard_limit": _decimal(row["monthly_hard_limit"]),
                "hard_limit_ratio": (
                    _decimal(row["consumed"]) / _decimal(row["monthly_hard_limit"])
                    if _decimal(row["monthly_hard_limit"]) > 0
                    else Decimal("0")
                ),
            }
            for row in budget_rows
        ]
        backup_age_seconds = (
            max((_utcnow() - backup["created_at"]).total_seconds(), 0)
            if backup is not None
            else None
        )
        return {
            "environment": environment.value,
            "observed_at": _utcnow().isoformat(),
            "api": {"healthy": api_healthy},
            "queue": {
                "ready": int(queue["ready"]),
                "running": int(queue["running"]),
                "stalled_ready": int(queue["stalled_ready"]),
                "expired_leases": int(queue["expired_leases"]),
                "dead_letter": int(queue["dead_letter"]),
            },
            "jobs": {
                "finished_in_window": finished,
                "failed_in_window": failed,
                "failure_rate": failure_rate,
                "average_duration_seconds": float(attempts["average_duration_seconds"]),
                "p95_duration_seconds": float(attempts["p95_duration_seconds"]),
            },
            "storage": {
                "capacity_bytes": storage_capacity_bytes,
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
                "free_ratio": free_ratio,
                "missing_objects": int(storage["missing_objects"]),
                "quarantined_objects": int(storage["quarantined_objects"]),
            },
            "budgets": budgets,
            "backup": {
                "latest_backup_set_id": str(backup["id"]) if backup else None,
                "latest_created_at": backup["created_at"].isoformat() if backup else None,
                "age_seconds": backup_age_seconds,
            },
            "thresholds": limits.model_dump(mode="json"),
        }

    def detect_alerts(
        self,
        *,
        environment: OperationsEnvironment,
        snapshot: dict[str, Any],
        actor: str,
    ) -> list[dict[str, Any]]:
        thresholds = MonitorThresholds(**snapshot["thresholds"])
        candidates: list[tuple[OperationsAlertKind, OperationsAlertSeverity, str, dict[str, Any]]] = []
        if not snapshot["api"]["healthy"]:
            candidates.append((
                OperationsAlertKind.API_UNHEALTHY,
                OperationsAlertSeverity.CRITICAL,
                "runtime-readiness",
                {"api": snapshot["api"]},
            ))
        if snapshot["queue"]["stalled_ready"] or snapshot["queue"]["expired_leases"]:
            candidates.append((
                OperationsAlertKind.QUEUE_STALLED,
                OperationsAlertSeverity.CRITICAL,
                "generation-jobs",
                {"queue": snapshot["queue"]},
            ))
        if (
            snapshot["queue"]["dead_letter"]
            or snapshot["jobs"]["failure_rate"] >= thresholds.failure_rate_warning
            or snapshot["jobs"]["p95_duration_seconds"] >= thresholds.job_duration_warning_seconds
        ):
            severity = (
                OperationsAlertSeverity.CRITICAL
                if snapshot["jobs"]["failure_rate"] >= thresholds.failure_rate_critical
                else OperationsAlertSeverity.WARNING
            )
            candidates.append((
                OperationsAlertKind.WORKER_FAILED,
                severity,
                "generation-attempts",
                {"queue": snapshot["queue"], "jobs": snapshot["jobs"]},
            ))
        if snapshot["storage"]["free_ratio"] <= thresholds.storage_warning_free_ratio:
            severity = (
                OperationsAlertSeverity.CRITICAL
                if snapshot["storage"]["free_ratio"] <= thresholds.storage_critical_free_ratio
                else OperationsAlertSeverity.WARNING
            )
            candidates.append((
                OperationsAlertKind.STORAGE_LOW,
                severity,
                "shared-storage",
                {"storage": snapshot["storage"]},
            ))
        critical_budgets = [
            item for item in snapshot["budgets"]
            if _decimal(item["hard_limit_ratio"]) >= Decimal(str(thresholds.budget_warning_ratio))
        ]
        if critical_budgets:
            severity = (
                OperationsAlertSeverity.CRITICAL
                if any(
                    _decimal(item["hard_limit_ratio"])
                    >= Decimal(str(thresholds.budget_critical_ratio))
                    for item in critical_budgets
                )
                else OperationsAlertSeverity.WARNING
            )
            candidates.append((
                OperationsAlertKind.BUDGET_THRESHOLD,
                severity,
                "production-budgets",
                {"budgets": critical_budgets},
            ))
        backup_age = snapshot["backup"]["age_seconds"]
        if backup_age is None or backup_age >= thresholds.backup_stale_seconds:
            candidates.append((
                OperationsAlertKind.BACKUP_STALE,
                OperationsAlertSeverity.CRITICAL if backup_age is None else OperationsAlertSeverity.WARNING,
                "operations-backup",
                {"backup": snapshot["backup"]},
            ))

        alerts: list[dict[str, Any]] = []
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            for kind, severity, source, details in candidates:
                details_digest = _hash(details)
                alert_key = f"{environment.value}:{kind.value}:{source}"
                row = conn.execute(
                    """INSERT INTO football_brief.operations_alert_events
                       (environment,alert_key,alert_kind,severity,source,details,details_digest)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                       ON CONFLICT (environment,alert_key,details_digest)
                       DO UPDATE SET alert_key=EXCLUDED.alert_key
                       RETURNING *""",
                    (
                        environment.value,
                        alert_key,
                        kind.value,
                        severity.value,
                        source,
                        _json(details),
                        details_digest,
                    ),
                ).fetchone()
                alerts.append(dict(row))
        return alerts

    def acknowledge_alert(self, *, alert_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            row = conn.execute(
                """UPDATE football_brief.operations_alert_events
                   SET status='acknowledged',acknowledged_by=%s,acknowledged_at=now()
                   WHERE id=%s AND status='open' RETURNING *""",
                (actor, alert_id),
            ).fetchone()
            if not row:
                raise OperationsError("operations_alert_not_open")
        return {"ok": True, "alert": dict(row)}

    def resolve_alert(self, *, alert_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_admin(conn, actor)
            row = conn.execute(
                """UPDATE football_brief.operations_alert_events
                   SET status='resolved',resolved_by=%s,resolved_at=now()
                   WHERE id=%s AND status IN ('open','acknowledged') RETURNING *""",
                (actor, alert_id),
            ).fetchone()
            if not row:
                raise OperationsError("operations_alert_not_resolvable")
        return {"ok": True, "alert": dict(row)}

    def list_drills(
        self,
        *,
        environment: OperationsEnvironment | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise OperationsError("invalid_operations_list_limit")
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.operations_drill_runs
                   WHERE (%s::text IS NULL OR environment=%s)
                   ORDER BY started_at DESC LIMIT %s""",
                (environment.value if environment else None, environment.value if environment else None, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _require_admin(conn: Any, actor: str) -> None:
        row = conn.execute(
            """SELECT ou.active,EXISTS(
                   SELECT 1 FROM football_brief.operator_user_roles our
                   WHERE our.operator_user_id=ou.id AND our.role='admin'
               ) AS is_admin
               FROM football_brief.operator_users ou WHERE ou.operator_id=%s""",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]) or not bool(row["is_admin"]):
            raise OperationsError("operations_admin_required")
