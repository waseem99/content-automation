from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID, uuid4

from src.application.generation_jobs.models import (
    GenerationAttemptStatus,
    GenerationJobCompletion,
    GenerationJobEnqueue,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobStatus,
    GenerationJobType,
    LegacyGenerationRecord,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class GenerationJobError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def canonical_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationJobService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def enqueue(self, request: GenerationJobEnqueue, *, actor: str) -> dict[str, Any]:
        fingerprint = canonical_fingerprint(request.input_payload)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            content = self._content_for_update(conn, request.portfolio_content_id)
            if int(content["version"]) != request.content_version:
                raise GenerationJobError(
                    "content_version_conflict",
                    details={"requested": request.content_version, "current": int(content["version"])},
                )
            self._validate_workflow_pair(
                conn,
                content_id=request.portfolio_content_id,
                workflow_id=request.production_workflow_id,
                workflow_version_id=request.production_workflow_version_id,
            )
            existing = conn.execute(
                "SELECT * FROM football_brief.generation_jobs WHERE idempotency_key=%s FOR UPDATE",
                (request.idempotency_key,),
            ).fetchone()
            if existing:
                self._validate_idempotent_reuse(existing, request, fingerprint)
                self._event(
                    conn,
                    job_id=existing["id"],
                    event="idempotent_reuse",
                    actor=actor,
                    details={"idempotency_key": request.idempotency_key},
                )
                result = dict(existing)
                result["reused"] = True
                return result

            dependency_rows = self._validate_dependencies(
                conn,
                dependency_ids=request.dependency_job_ids,
                content_id=request.portfolio_content_id,
                content_version=request.content_version,
            )
            row = conn.execute(
                """INSERT INTO football_brief.generation_jobs
                   (portfolio_content_id, content_version, production_workflow_id,
                    production_workflow_version_id, job_type, provider, model_id,
                    preferred_worker_id, priority, idempotency_key, input_fingerprint,
                    input_payload, timeout_seconds, max_attempts, estimated_cost_usd,
                    reserved_cost_usd, legacy_source, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.portfolio_content_id,
                    request.content_version,
                    request.production_workflow_id,
                    request.production_workflow_version_id,
                    request.job_type.value,
                    request.provider,
                    request.model_id,
                    request.preferred_worker_id,
                    request.priority,
                    request.idempotency_key,
                    fingerprint,
                    _json(request.input_payload),
                    request.timeout_seconds,
                    request.max_attempts,
                    request.estimated_cost_usd,
                    request.reserved_cost_usd,
                    _json(request.legacy_source),
                    actor,
                ),
            ).fetchone()
            for dependency in dependency_rows:
                conn.execute(
                    """INSERT INTO football_brief.generation_job_dependencies
                       (job_id, depends_on_job_id) VALUES (%s,%s)""",
                    (row["id"], dependency["id"]),
                )
            self._event(
                conn,
                job_id=row["id"],
                event="enqueued",
                actor=actor,
                details={
                    "job_type": request.job_type.value,
                    "content_version": request.content_version,
                    "dependency_count": len(dependency_rows),
                },
            )
        result = dict(row)
        result["reused"] = False
        return result

    def detail(self, *, job_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            job = conn.execute(
                """SELECT j.*, mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                          pc.version AS current_content_version
                   FROM football_brief.generation_jobs j
                   JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE j.id=%s""",
                (job_id,),
            ).fetchone()
            if not job:
                raise GenerationJobError("generation_job_not_found")
            attempts = conn.execute(
                """SELECT * FROM football_brief.generation_job_attempts
                   WHERE job_id=%s ORDER BY attempt_number""",
                (job_id,),
            ).fetchall()
            events = conn.execute(
                """SELECT * FROM football_brief.generation_job_events
                   WHERE job_id=%s ORDER BY created_at, id""",
                (job_id,),
            ).fetchall()
            dependencies = conn.execute(
                """SELECT d.depends_on_job_id, parent.job_type, parent.status,
                          parent.content_version, parent.output_fingerprint
                   FROM football_brief.generation_job_dependencies d
                   JOIN football_brief.generation_jobs parent ON parent.id=d.depends_on_job_id
                   WHERE d.job_id=%s ORDER BY d.created_at, d.depends_on_job_id""",
                (job_id,),
            ).fetchall()
        return {
            "ok": True,
            "job": dict(job),
            "attempts": [dict(row) for row in attempts],
            "events": [dict(row) for row in events],
            "dependencies": [dict(row) for row in dependencies],
        }

    def list_jobs(
        self,
        *,
        brand_ids: Iterable[UUID] | None = None,
        statuses: Iterable[GenerationJobStatus | str] = (),
        job_types: Iterable[GenerationJobType | str] = (),
        worker_id: str | None = None,
        content_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise GenerationJobError("invalid_queue_limit")
        conditions = ["true"]
        values: list[Any] = []
        normalized_brands = [UUID(str(value)) for value in brand_ids] if brand_ids is not None else None
        if normalized_brands is not None:
            if not normalized_brands:
                return []
            conditions.append("mp.brand_id = ANY(%s::uuid[])")
            values.append(normalized_brands)
        normalized_statuses = [GenerationJobStatus(value).value for value in statuses]
        if normalized_statuses:
            conditions.append("j.status = ANY(%s::text[])")
            values.append(normalized_statuses)
        normalized_types = [GenerationJobType(value).value for value in job_types]
        if normalized_types:
            conditions.append("j.job_type = ANY(%s::text[])")
            values.append(normalized_types)
        if worker_id:
            conditions.append("j.current_worker_id=%s")
            values.append(worker_id)
        if content_id:
            conditions.append("j.portfolio_content_id=%s")
            values.append(content_id)
        values.append(limit)
        sql = f"""SELECT j.*, mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                         pc.version AS current_content_version,
                         EXISTS (
                            SELECT 1 FROM football_brief.generation_job_dependencies d
                            JOIN football_brief.generation_jobs parent ON parent.id=d.depends_on_job_id
                            WHERE d.job_id=j.id AND parent.status<>'succeeded'
                         ) AS dependency_blocked
                  FROM football_brief.generation_jobs j
                  JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
                  JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                  JOIN football_brief.brands b ON b.id=mp.brand_id
                  WHERE {' AND '.join(conditions)}
                  ORDER BY
                    CASE j.status
                      WHEN 'running' THEN 0 WHEN 'failed' THEN 1 WHEN 'queued' THEN 2
                      WHEN 'dead_letter' THEN 3 WHEN 'cancelled' THEN 4 ELSE 5
                    END,
                    j.priority DESC, j.available_at, j.queued_at, j.id
                  LIMIT %s"""
        with self.database.connection() as conn:
            rows = conn.execute(sql, tuple(values)).fetchall()
        return [dict(row) for row in rows]

    def claim(
        self,
        *,
        worker_id: str,
        allowed_brand_ids: Iterable[UUID] | None,
        allowed_job_types: Iterable[GenerationJobType | str],
        requested_job_types: Iterable[GenerationJobType | str] = (),
        providers: Iterable[str] = (),
        lease_seconds: int = 120,
    ) -> dict[str, Any] | None:
        if not 15 <= lease_seconds <= 3600:
            raise GenerationJobError("invalid_lease_seconds")
        allowed_types = {GenerationJobType(value).value for value in allowed_job_types}
        requested_types = {GenerationJobType(value).value for value in requested_job_types}
        selected_types = requested_types or allowed_types
        if not selected_types.issubset(allowed_types):
            raise GenerationJobError("worker_job_type_not_allowed")
        if not selected_types:
            return None
        normalized_providers = sorted({str(value).strip() for value in providers if str(value).strip()})
        normalized_brands = [UUID(str(value)) for value in allowed_brand_ids] if allowed_brand_ids is not None else None
        if normalized_brands is not None and not normalized_brands:
            return None
        now = _utcnow()
        lease_until = now + timedelta(seconds=lease_seconds)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, worker_id)
            self._recover_stale_locked(conn, actor=worker_id, limit=25, now=now)
            conditions = [
                "j.status='queued'",
                "j.available_at<=%s",
                "j.attempt_count<j.max_attempts",
                "pc.version=j.content_version",
                "j.job_type = ANY(%s::text[])",
                "(j.preferred_worker_id IS NULL OR j.preferred_worker_id=%s)",
                "NOT EXISTS ("
                " SELECT 1 FROM football_brief.generation_job_dependencies d"
                " JOIN football_brief.generation_jobs parent ON parent.id=d.depends_on_job_id"
                " WHERE d.job_id=j.id AND parent.status<>'succeeded'"
                ")",
            ]
            values: list[Any] = [now, sorted(selected_types), worker_id]
            if normalized_brands is not None:
                conditions.append("mp.brand_id = ANY(%s::uuid[])")
                values.append(normalized_brands)
            if normalized_providers:
                conditions.append("j.provider = ANY(%s::text[])")
                values.append(normalized_providers)
            row = conn.execute(
                f"""SELECT j.*, mp.brand_id, pc.version AS current_content_version
                    FROM football_brief.generation_jobs j
                    JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY j.priority DESC, j.available_at, j.queued_at, j.id
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT 1""",
                tuple(values),
            ).fetchone()
            if not row:
                return None
            attempt_id = uuid4()
            lease_token = uuid4()
            attempt_number = int(row["attempt_count"]) + 1
            attempt = conn.execute(
                """INSERT INTO football_brief.generation_job_attempts
                   (id, job_id, attempt_number, lease_token, worker_id, status,
                    input_fingerprint, claimed_at, heartbeat_at, lease_expires_at)
                   VALUES (%s,%s,%s,%s,%s,'running',%s,%s,%s,%s)
                   RETURNING *""",
                (
                    attempt_id,
                    row["id"],
                    attempt_number,
                    lease_token,
                    worker_id,
                    row["input_fingerprint"],
                    now,
                    now,
                    lease_until,
                ),
            ).fetchone()
            job = conn.execute(
                """UPDATE football_brief.generation_jobs
                   SET status='running', attempt_count=attempt_count+1,
                       current_attempt_id=%s, current_worker_id=%s,
                       started_at=COALESCE(started_at,%s), heartbeat_at=%s,
                       lease_expires_at=%s, finished_at=NULL,
                       error_code=NULL, error_message=NULL, error_details='{}'::jsonb
                   WHERE id=%s AND status='queued'
                   RETURNING *""",
                (attempt_id, worker_id, now, now, lease_until, row["id"]),
            ).fetchone()
            if not job:
                raise GenerationJobError("generation_job_claim_conflict")
            self._event(
                conn,
                job_id=job["id"],
                attempt_id=attempt_id,
                event="claimed",
                actor=worker_id,
                details={"attempt_number": attempt_number, "lease_expires_at": lease_until.isoformat()},
            )
        return {
            "ok": True,
            "job": dict(job),
            "attempt": dict(attempt),
            "lease_token": lease_token,
        }

    def heartbeat(self, request: GenerationJobHeartbeat) -> dict[str, Any]:
        now = _utcnow()
        lease_until = now + timedelta(seconds=request.lease_seconds)
        with self.database.transaction() as conn:
            row = self._current_attempt_for_update(
                conn,
                job_id=request.job_id,
                attempt_id=request.attempt_id,
            )
            self._validate_live_lease(row, request.worker_id, request.lease_token, now)
            conn.execute(
                """UPDATE football_brief.generation_job_attempts
                   SET heartbeat_at=%s, lease_expires_at=%s
                   WHERE id=%s""",
                (now, lease_until, request.attempt_id),
            )
            job = conn.execute(
                """UPDATE football_brief.generation_jobs
                   SET heartbeat_at=%s, lease_expires_at=%s
                   WHERE id=%s RETURNING *""",
                (now, lease_until, request.job_id),
            ).fetchone()
            self._event(
                conn,
                job_id=request.job_id,
                attempt_id=request.attempt_id,
                event="heartbeat",
                actor=request.worker_id,
                details={"lease_expires_at": lease_until.isoformat()},
            )
        return {"ok": True, "job": dict(job), "lease_expires_at": lease_until}

    def complete(self, request: GenerationJobCompletion) -> dict[str, Any]:
        now = _utcnow()
        fingerprint = canonical_fingerprint(request.output_payload)
        superseded: dict[str, Any] | None = None
        with self.database.transaction() as conn:
            row = self._current_attempt_for_update(
                conn,
                job_id=request.job_id,
                attempt_id=request.attempt_id,
            )
            self._validate_live_lease(row, request.worker_id, request.lease_token, now)
            if int(row["current_content_version"]) != int(row["content_version"]):
                self._abandon_for_superseded_content(conn, row=row, now=now, actor=request.worker_id)
                superseded = {
                    "job_id": str(request.job_id),
                    "job_content_version": int(row["content_version"]),
                    "current_content_version": int(row["current_content_version"]),
                }
            else:
                conn.execute(
                    """UPDATE football_brief.generation_job_attempts
                       SET status='succeeded', output_fingerprint=%s, output_payload=%s::jsonb,
                           provider_request_id=%s, actual_cost_usd=%s, finished_at=%s
                       WHERE id=%s""",
                    (
                        fingerprint,
                        _json(request.output_payload),
                        request.provider_request_id,
                        request.actual_cost_usd,
                        now,
                        request.attempt_id,
                    ),
                )
                job = conn.execute(
                    """UPDATE football_brief.generation_jobs
                       SET status='succeeded', output_fingerprint=%s, output_payload=%s::jsonb,
                           actual_cost_usd=actual_cost_usd+%s, finished_at=%s,
                           heartbeat_at=NULL, lease_expires_at=NULL,
                           error_code=NULL, error_message=NULL, error_details='{}'::jsonb
                       WHERE id=%s AND status='running' RETURNING *""",
                    (
                        fingerprint,
                        _json(request.output_payload),
                        request.actual_cost_usd,
                        now,
                        request.job_id,
                    ),
                ).fetchone()
                if not job:
                    raise GenerationJobError("generation_job_completion_conflict")
                self._event(
                    conn,
                    job_id=request.job_id,
                    attempt_id=request.attempt_id,
                    event="succeeded",
                    actor=request.worker_id,
                    details={
                        "output_fingerprint": fingerprint,
                        "actual_cost_usd": str(request.actual_cost_usd),
                    },
                )
        if superseded is not None:
            raise GenerationJobError("content_version_superseded", details=superseded)
        return {"ok": True, "job": dict(job)}

    def fail(self, request: GenerationJobFailure) -> dict[str, Any]:
        now = _utcnow()
        with self.database.transaction() as conn:
            row = self._current_attempt_for_update(
                conn,
                job_id=request.job_id,
                attempt_id=request.attempt_id,
            )
            self._validate_live_lease(row, request.worker_id, request.lease_token, now)
            exhausted = int(row["attempt_count"]) >= int(row["max_attempts"])
            next_status = GenerationJobStatus.DEAD_LETTER if exhausted else GenerationJobStatus.FAILED
            details = dict(request.error_details)
            details["retryable"] = bool(request.retryable)
            conn.execute(
                """UPDATE football_brief.generation_job_attempts
                   SET status='failed', retryable=%s, error_code=%s, error_message=%s,
                       error_details=%s::jsonb, actual_cost_usd=%s, finished_at=%s
                   WHERE id=%s""",
                (
                    request.retryable,
                    request.error_code,
                    request.error_message,
                    _json(details),
                    request.actual_cost_usd,
                    now,
                    request.attempt_id,
                ),
            )
            job = conn.execute(
                """UPDATE football_brief.generation_jobs
                   SET status=%s, actual_cost_usd=actual_cost_usd+%s,
                       error_code=%s, error_message=%s, error_details=%s::jsonb,
                       finished_at=%s, heartbeat_at=NULL, lease_expires_at=NULL
                   WHERE id=%s AND status='running' RETURNING *""",
                (
                    next_status.value,
                    request.actual_cost_usd,
                    request.error_code,
                    request.error_message,
                    _json(details),
                    now,
                    request.job_id,
                ),
            ).fetchone()
            if not job:
                raise GenerationJobError("generation_job_failure_conflict")
            self._event(
                conn,
                job_id=request.job_id,
                attempt_id=request.attempt_id,
                event="failed",
                actor=request.worker_id,
                details={
                    "retryable": request.retryable,
                    "attempt_count": int(row["attempt_count"]),
                    "max_attempts": int(row["max_attempts"]),
                    "error_code": request.error_code,
                },
            )
            if exhausted:
                self._event(
                    conn,
                    job_id=request.job_id,
                    attempt_id=request.attempt_id,
                    event="dead_lettered",
                    actor=request.worker_id,
                    details={"reason": "attempt_limit_exhausted"},
                )
        return {"ok": True, "job": dict(job), "dead_lettered": exhausted}

    def retry(self, *, job_id: UUID, actor: str, delay_seconds: int = 0) -> dict[str, Any]:
        if not 0 <= delay_seconds <= 86400:
            raise GenerationJobError("invalid_retry_delay")
        now = _utcnow()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """SELECT j.*, pc.version AS current_content_version
                   FROM football_brief.generation_jobs j
                   JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
                   WHERE j.id=%s FOR UPDATE OF j""",
                (job_id,),
            ).fetchone()
            if not row:
                raise GenerationJobError("generation_job_not_found")
            if row["status"] != GenerationJobStatus.FAILED.value:
                raise GenerationJobError("generation_job_not_retryable", details={"status": row["status"]})
            if not bool((row["error_details"] or {}).get("retryable")):
                raise GenerationJobError("generation_job_failure_not_retryable")
            if int(row["attempt_count"]) >= int(row["max_attempts"]):
                raise GenerationJobError("generation_job_attempt_limit_reached")
            if int(row["current_content_version"]) != int(row["content_version"]):
                self._dead_letter_superseded(conn, row=row, now=now, actor=actor)
                superseded = True
            else:
                available_at = now + timedelta(seconds=delay_seconds)
                job = conn.execute(
                    """UPDATE football_brief.generation_jobs
                       SET status='queued', current_attempt_id=NULL, current_worker_id=NULL,
                           heartbeat_at=NULL, lease_expires_at=NULL, finished_at=NULL,
                           available_at=%s, queued_at=%s
                       WHERE id=%s RETURNING *""",
                    (available_at, now, job_id),
                ).fetchone()
                self._event(
                    conn,
                    job_id=job_id,
                    event="retried",
                    actor=actor,
                    details={"available_at": available_at.isoformat()},
                )
                superseded = False
        if superseded:
            raise GenerationJobError("content_version_superseded")
        return {"ok": True, "job": dict(job)}

    def cancel(self, *, job_id: UUID, actor: str, reason: str) -> dict[str, Any]:
        if len(reason.strip()) < 3:
            raise GenerationJobError("cancellation_reason_required")
        now = _utcnow()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                "SELECT * FROM football_brief.generation_jobs WHERE id=%s FOR UPDATE",
                (job_id,),
            ).fetchone()
            if not row:
                raise GenerationJobError("generation_job_not_found")
            if row["status"] in {
                GenerationJobStatus.SUCCEEDED.value,
                GenerationJobStatus.CANCELLED.value,
                GenerationJobStatus.DEAD_LETTER.value,
            }:
                raise GenerationJobError("generation_job_terminal", details={"status": row["status"]})
            if row["status"] == GenerationJobStatus.RUNNING.value and row["current_attempt_id"]:
                conn.execute(
                    """UPDATE football_brief.generation_job_attempts
                       SET status='cancelled', error_code='cancelled_by_operator',
                           error_message=%s, finished_at=%s
                       WHERE id=%s AND status='running'""",
                    (reason, now, row["current_attempt_id"]),
                )
            job = conn.execute(
                """UPDATE football_brief.generation_jobs
                   SET status='cancelled', cancelled_at=%s, cancelled_by=%s,
                       finished_at=%s, heartbeat_at=NULL, lease_expires_at=NULL,
                       error_code='cancelled_by_operator', error_message=%s,
                       error_details=%s::jsonb
                   WHERE id=%s RETURNING *""",
                (now, actor, now, reason, _json({"reason": reason}), job_id),
            ).fetchone()
            self._event(
                conn,
                job_id=job_id,
                attempt_id=row["current_attempt_id"],
                event="cancelled",
                actor=actor,
                details={"reason": reason, "previous_status": row["status"]},
            )
        return {"ok": True, "job": dict(job)}

    def recover_stale(self, *, actor: str, limit: int = 100) -> dict[str, int]:
        if not 1 <= limit <= 1000:
            raise GenerationJobError("invalid_recovery_limit")
        now = _utcnow()
        with self.database.transaction() as conn:
            recovered, dead_lettered = self._recover_stale_locked(
                conn,
                actor=actor,
                limit=limit,
                now=now,
            )
            superseded = self._supersede_stale_queued_locked(conn, actor=actor, limit=limit, now=now)
        return {
            "recovered": recovered,
            "dead_lettered": dead_lettered,
            "content_version_superseded": superseded,
        }

    def import_legacy_terminal(
        self,
        *,
        content_id: UUID,
        content_version: int,
        source_name: str,
        record: LegacyGenerationRecord,
        actor: str,
    ) -> dict[str, Any]:
        normalized_status = record.status.strip().lower()
        status_map = {
            "succeeded": GenerationJobStatus.SUCCEEDED,
            "success": GenerationJobStatus.SUCCEEDED,
            "complete": GenerationJobStatus.SUCCEEDED,
            "completed": GenerationJobStatus.SUCCEEDED,
            "failed": GenerationJobStatus.FAILED,
            "error": GenerationJobStatus.FAILED,
            "cancelled": GenerationJobStatus.CANCELLED,
            "canceled": GenerationJobStatus.CANCELLED,
            "dead_letter": GenerationJobStatus.DEAD_LETTER,
        }
        target = status_map.get(normalized_status)
        if target is None:
            raise GenerationJobError("legacy_status_not_terminal")
        if target == GenerationJobStatus.SUCCEEDED and not record.output_payload:
            raise GenerationJobError("legacy_success_output_required")
        idempotency_key = f"legacy:{source_name.strip()}:{record.legacy_id.strip()}"
        input_fingerprint = canonical_fingerprint(record.input_payload)
        output_fingerprint = canonical_fingerprint(record.output_payload) if record.output_payload else None
        now = _utcnow()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            content = self._content_for_update(conn, content_id)
            if content_version > int(content["version"]):
                raise GenerationJobError("legacy_content_version_in_future")
            existing = conn.execute(
                "SELECT * FROM football_brief.generation_jobs WHERE idempotency_key=%s FOR UPDATE",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if (
                    str(existing["portfolio_content_id"]) != str(content_id)
                    or int(existing["content_version"]) != content_version
                    or existing["input_fingerprint"] != input_fingerprint
                ):
                    raise GenerationJobError("idempotency_conflict")
                result = dict(existing)
                result["reused"] = True
                return result
            attempts = max(1, record.attempt_count)
            final_attempt_id = uuid4()
            legacy_source = {
                "source": source_name,
                "legacy_id": record.legacy_id,
                "metadata": record.metadata,
                "imported_status": normalized_status,
            }
            error_details = {"legacy": True, **record.metadata}
            if target == GenerationJobStatus.FAILED:
                error_details["retryable"] = bool(record.metadata.get("retryable", False))
            job = conn.execute(
                """INSERT INTO football_brief.generation_jobs
                   (portfolio_content_id, content_version, job_type, provider, model_id,
                    status, idempotency_key, input_fingerprint, input_payload,
                    output_fingerprint, output_payload, max_attempts, attempt_count,
                    current_attempt_id, current_worker_id, actual_cost_usd,
                    started_at, finished_at, cancelled_at, cancelled_by,
                    error_code, error_message, error_details, legacy_source, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s,
                           %s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                   RETURNING *""",
                (
                    content_id,
                    content_version,
                    record.job_type.value,
                    record.provider,
                    record.model_id,
                    target.value,
                    idempotency_key,
                    input_fingerprint,
                    _json(record.input_payload),
                    output_fingerprint,
                    _json(record.output_payload) if record.output_payload is not None else None,
                    max(attempts, 3),
                    attempts,
                    final_attempt_id,
                    record.worker_id or f"legacy:{source_name}",
                    record.actual_cost_usd,
                    now,
                    now,
                    now if target == GenerationJobStatus.CANCELLED else None,
                    actor if target == GenerationJobStatus.CANCELLED else None,
                    record.error_code,
                    record.error_message,
                    _json(error_details),
                    _json(legacy_source),
                    actor,
                ),
            ).fetchone()
            for attempt_number in range(1, attempts):
                conn.execute(
                    """INSERT INTO football_brief.generation_job_attempts
                       (job_id, attempt_number, worker_id, status, input_fingerprint,
                        retryable, error_code, error_message, error_details,
                        claimed_at, heartbeat_at, lease_expires_at, finished_at)
                       VALUES (%s,%s,%s,'abandoned',%s,true,'legacy_attempt_unknown',
                               'Legacy ledger did not retain this attempt payload',%s::jsonb,
                               %s,%s,%s,%s)""",
                    (
                        job["id"],
                        attempt_number,
                        record.worker_id or f"legacy:{source_name}",
                        input_fingerprint,
                        _json({"legacy": True}),
                        now,
                        now,
                        now,
                        now,
                    ),
                )
            attempt_status = {
                GenerationJobStatus.SUCCEEDED: GenerationAttemptStatus.SUCCEEDED,
                GenerationJobStatus.FAILED: GenerationAttemptStatus.FAILED,
                GenerationJobStatus.CANCELLED: GenerationAttemptStatus.CANCELLED,
                GenerationJobStatus.DEAD_LETTER: GenerationAttemptStatus.FAILED,
            }[target]
            conn.execute(
                """INSERT INTO football_brief.generation_job_attempts
                   (id, job_id, attempt_number, worker_id, status, input_fingerprint,
                    output_fingerprint, output_payload, actual_cost_usd, retryable,
                    error_code, error_message, error_details, claimed_at, heartbeat_at,
                    lease_expires_at, finished_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
                (
                    final_attempt_id,
                    job["id"],
                    attempts,
                    record.worker_id or f"legacy:{source_name}",
                    attempt_status.value,
                    input_fingerprint,
                    output_fingerprint,
                    _json(record.output_payload) if record.output_payload is not None else None,
                    record.actual_cost_usd,
                    bool(record.metadata.get("retryable", False)),
                    record.error_code,
                    record.error_message,
                    _json(error_details),
                    now,
                    now,
                    now,
                    now,
                ),
            )
            self._event(
                conn,
                job_id=job["id"],
                attempt_id=final_attempt_id,
                event="legacy_imported",
                actor=actor,
                details=legacy_source,
            )
        result = dict(job)
        result["reused"] = False
        return result

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not row:
            raise GenerationJobError("operator_inactive_or_missing")

    @staticmethod
    def _content_for_update(conn, content_id: UUID):
        row = conn.execute(
            """SELECT pc.id, pc.version, mp.brand_id
               FROM football_brief.portfolio_content pc
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE pc.id=%s FOR UPDATE OF pc""",
            (content_id,),
        ).fetchone()
        if not row:
            raise GenerationJobError("content_not_found")
        return row

    @staticmethod
    def _validate_workflow_pair(
        conn,
        *,
        content_id: UUID,
        workflow_id: UUID | None,
        workflow_version_id: UUID | None,
    ) -> None:
        if workflow_id is None:
            return
        if workflow_version_id is None:
            row = conn.execute(
                """SELECT id FROM football_brief.production_workflows
                   WHERE id=%s AND portfolio_content_id=%s""",
                (workflow_id, content_id),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT v.id FROM football_brief.production_workflow_versions v
                   JOIN football_brief.production_workflows w ON w.id=v.workflow_id
                   WHERE w.id=%s AND v.id=%s AND w.portfolio_content_id=%s""",
                (workflow_id, workflow_version_id, content_id),
            ).fetchone()
        if not row:
            raise GenerationJobError("workflow_job_binding_invalid")

    @staticmethod
    def _validate_idempotent_reuse(existing, request: GenerationJobEnqueue, fingerprint: str) -> None:
        immutable = {
            "portfolio_content_id": str(request.portfolio_content_id),
            "content_version": request.content_version,
            "job_type": request.job_type.value,
            "provider": request.provider,
            "model_id": request.model_id,
            "input_fingerprint": fingerprint,
        }
        mismatches = {
            key: {"existing": str(existing[key]) if existing[key] is not None else None, "requested": str(value) if value is not None else None}
            for key, value in immutable.items()
            if (str(existing[key]) if existing[key] is not None else None)
            != (str(value) if value is not None else None)
        }
        if mismatches:
            raise GenerationJobError("idempotency_conflict", details={"mismatches": mismatches})

    @staticmethod
    def _validate_dependencies(
        conn,
        *,
        dependency_ids: Iterable[UUID],
        content_id: UUID,
        content_version: int,
    ) -> list[Any]:
        rows = []
        for dependency_id in dependency_ids:
            row = conn.execute(
                """SELECT id, portfolio_content_id, content_version, status
                   FROM football_brief.generation_jobs WHERE id=%s""",
                (dependency_id,),
            ).fetchone()
            if not row:
                raise GenerationJobError("dependency_job_not_found", details={"job_id": str(dependency_id)})
            if str(row["portfolio_content_id"]) != str(content_id) or int(row["content_version"]) != content_version:
                raise GenerationJobError("dependency_content_version_mismatch")
            rows.append(row)
        return rows

    @staticmethod
    def _current_attempt_for_update(conn, *, job_id: UUID, attempt_id: UUID):
        row = conn.execute(
            """SELECT j.*, a.status AS attempt_status, a.lease_token,
                      a.worker_id AS attempt_worker_id,
                      a.lease_expires_at AS attempt_lease_expires_at,
                      pc.version AS current_content_version
               FROM football_brief.generation_jobs j
               JOIN football_brief.generation_job_attempts a ON a.id=j.current_attempt_id
               JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
               WHERE j.id=%s AND a.id=%s
               FOR UPDATE OF j, a, pc""",
            (job_id, attempt_id),
        ).fetchone()
        if not row:
            raise GenerationJobError("generation_job_attempt_not_current")
        return row

    @staticmethod
    def _validate_live_lease(row, worker_id: str, lease_token: UUID, now: datetime) -> None:
        if row["status"] != GenerationJobStatus.RUNNING.value:
            raise GenerationJobError("generation_job_not_running", details={"status": row["status"]})
        if row["attempt_status"] != GenerationAttemptStatus.RUNNING.value:
            raise GenerationJobError("generation_attempt_not_running")
        if row["attempt_worker_id"] != worker_id or row["current_worker_id"] != worker_id:
            raise GenerationJobError("generation_job_worker_mismatch")
        if str(row["lease_token"]) != str(lease_token):
            raise GenerationJobError("generation_job_lease_token_invalid")
        if row["attempt_lease_expires_at"] <= now or row["lease_expires_at"] <= now:
            raise GenerationJobError("generation_job_lease_expired")

    def _recover_stale_locked(self, conn, *, actor: str, limit: int, now: datetime) -> tuple[int, int]:
        rows = conn.execute(
            """SELECT * FROM football_brief.generation_jobs
               WHERE status='running' AND lease_expires_at<=%s
               ORDER BY lease_expires_at, id
               FOR UPDATE SKIP LOCKED
               LIMIT %s""",
            (now, limit),
        ).fetchall()
        recovered = 0
        dead_lettered = 0
        for row in rows:
            if row["current_attempt_id"]:
                conn.execute(
                    """UPDATE football_brief.generation_job_attempts
                       SET status='timed_out', retryable=true,
                           error_code='worker_lease_expired',
                           error_message='Worker heartbeat lease expired',
                           error_details=%s::jsonb, finished_at=%s
                       WHERE id=%s AND status='running'""",
                    (_json({"lease_expires_at": str(row["lease_expires_at"])}), now, row["current_attempt_id"]),
                )
            exhausted = int(row["attempt_count"]) >= int(row["max_attempts"])
            if exhausted:
                conn.execute(
                    """UPDATE football_brief.generation_jobs
                       SET status='dead_letter', finished_at=%s,
                           heartbeat_at=NULL, lease_expires_at=NULL,
                           error_code='worker_lease_expired',
                           error_message='Worker lease expired and attempt limit was exhausted',
                           error_details=%s::jsonb
                       WHERE id=%s""",
                    (now, _json({"retryable": True}), row["id"]),
                )
                dead_lettered += 1
                next_event = "dead_lettered"
            else:
                conn.execute(
                    """UPDATE football_brief.generation_jobs
                       SET status='queued', current_attempt_id=NULL, current_worker_id=NULL,
                           heartbeat_at=NULL, lease_expires_at=NULL, finished_at=NULL,
                           available_at=%s, queued_at=%s,
                           error_code='worker_lease_expired',
                           error_message='Recovered after worker heartbeat lease expired',
                           error_details=%s::jsonb
                       WHERE id=%s""",
                    (now, now, _json({"retryable": True}), row["id"]),
                )
                recovered += 1
                next_event = "recovered"
            self._event(
                conn,
                job_id=row["id"],
                attempt_id=row["current_attempt_id"],
                event="timed_out",
                actor=actor,
                details={"attempt_count": int(row["attempt_count"])},
            )
            self._event(
                conn,
                job_id=row["id"],
                attempt_id=row["current_attempt_id"],
                event=next_event,
                actor=actor,
                details={"reason": "worker_lease_expired"},
            )
        return recovered, dead_lettered

    def _supersede_stale_queued_locked(self, conn, *, actor: str, limit: int, now: datetime) -> int:
        rows = conn.execute(
            """SELECT j.* FROM football_brief.generation_jobs j
               JOIN football_brief.portfolio_content pc ON pc.id=j.portfolio_content_id
               WHERE j.status IN ('queued','failed') AND pc.version<>j.content_version
               ORDER BY j.queued_at, j.id
               FOR UPDATE OF j SKIP LOCKED
               LIMIT %s""",
            (limit,),
        ).fetchall()
        for row in rows:
            self._dead_letter_superseded(conn, row=row, now=now, actor=actor)
        return len(rows)

    def _abandon_for_superseded_content(self, conn, *, row, now: datetime, actor: str) -> None:
        conn.execute(
            """UPDATE football_brief.generation_job_attempts
               SET status='abandoned', retryable=false,
                   error_code='content_version_superseded',
                   error_message='Content version changed before output registration',
                   error_details=%s::jsonb, finished_at=%s
               WHERE id=%s AND status='running'""",
            (
                _json({"job_content_version": int(row["content_version"]), "current_content_version": int(row["current_content_version"])}),
                now,
                row["current_attempt_id"],
            ),
        )
        conn.execute(
            """UPDATE football_brief.generation_jobs
               SET status='dead_letter', finished_at=%s,
                   heartbeat_at=NULL, lease_expires_at=NULL,
                   error_code='content_version_superseded',
                   error_message='Content version changed before output registration',
                   error_details=%s::jsonb
               WHERE id=%s""",
            (
                now,
                _json({"job_content_version": int(row["content_version"]), "current_content_version": int(row["current_content_version"])}),
                row["id"],
            ),
        )
        self._event(
            conn,
            job_id=row["id"],
            attempt_id=row["current_attempt_id"],
            event="content_version_superseded",
            actor=actor,
            details={"current_content_version": int(row["current_content_version"])},
        )
        self._event(
            conn,
            job_id=row["id"],
            attempt_id=row["current_attempt_id"],
            event="dead_lettered",
            actor=actor,
            details={"reason": "content_version_superseded"},
        )

    def _dead_letter_superseded(self, conn, *, row, now: datetime, actor: str) -> None:
        conn.execute(
            """UPDATE football_brief.generation_jobs
               SET status='dead_letter', finished_at=%s,
                   current_attempt_id=CASE WHEN status='queued' THEN NULL ELSE current_attempt_id END,
                   current_worker_id=NULL, heartbeat_at=NULL, lease_expires_at=NULL,
                   error_code='content_version_superseded',
                   error_message='Queued work belongs to an older content version',
                   error_details=%s::jsonb
               WHERE id=%s""",
            (now, _json({"retryable": False}), row["id"]),
        )
        self._event(
            conn,
            job_id=row["id"],
            attempt_id=row["current_attempt_id"],
            event="content_version_superseded",
            actor=actor,
            details={"job_content_version": int(row["content_version"])},
        )
        self._event(
            conn,
            job_id=row["id"],
            attempt_id=row["current_attempt_id"],
            event="dead_lettered",
            actor=actor,
            details={"reason": "content_version_superseded"},
        )

    @staticmethod
    def _event(
        conn,
        *,
        job_id: UUID,
        event: str,
        actor: str | None,
        details: dict[str, Any],
        attempt_id: UUID | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.generation_job_events
               (job_id, attempt_id, event, actor, details)
               VALUES (%s,%s,%s,%s,%s::jsonb)""",
            (job_id, attempt_id, event, actor, _json(details)),
        )
