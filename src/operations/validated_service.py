from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.operations.models import (
    MonitorThresholds,
    OperationsAlertKind,
    OperationsAlertSeverity,
    OperationsEnvironment,
)
from src.operations.service import OperationsService, _decimal, _hash, _json, _utcnow


class ValidatedOperationsService(OperationsService):
    """Correct monitoring schema bindings and immutable alert deduplication."""

    def snapshot(
        self,
        *,
        environment: OperationsEnvironment,
        api_healthy: bool,
        storage_capacity_bytes: int,
        thresholds: MonitorThresholds | None = None,
    ) -> dict[str, Any]:
        if storage_capacity_bytes <= 0:
            from src.operations.service import OperationsError

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
                       count(*) FILTER (
                           WHERE status IN ('failed','superseded') AND finished_at IS NOT NULL
                       ) AS failed,
                       COALESCE(avg(extract(epoch FROM (finished_at-started_at)))
                           FILTER (WHERE finished_at IS NOT NULL),0) AS average_duration_seconds,
                       COALESCE(percentile_cont(0.95) WITHIN GROUP (
                           ORDER BY extract(epoch FROM (finished_at-started_at))
                       ) FILTER (WHERE finished_at IS NOT NULL),0) AS p95_duration_seconds
                   FROM football_brief.generation_job_attempts
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
        candidates: list[
            tuple[OperationsAlertKind, OperationsAlertSeverity, str, dict[str, Any]]
        ] = []
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
                "generation-job-attempts",
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
            item
            for item in snapshot["budgets"]
            if _decimal(item["hard_limit_ratio"])
            >= Decimal(str(thresholds.budget_warning_ratio))
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
                (
                    OperationsAlertSeverity.CRITICAL
                    if backup_age is None
                    else OperationsAlertSeverity.WARNING
                ),
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
                       DO NOTHING
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
                if row is None:
                    row = conn.execute(
                        """SELECT * FROM football_brief.operations_alert_events
                           WHERE environment=%s AND alert_key=%s AND details_digest=%s""",
                        (environment.value, alert_key, details_digest),
                    ).fetchone()
                alerts.append(dict(row))
        return alerts
