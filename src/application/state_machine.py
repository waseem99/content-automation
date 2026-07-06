from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.workflow_models import StageExecutionCreate
from src.domain.workflow_state_models import (
    ResumePlan,
    StageDependencyCreate,
    StageTransitionRequest,
    TransitionActorType,
    TransitionReasonCode,
    WorkflowTransitionRequest,
)
from src.domain.workflow_status import StageStatus, WorkflowStatus
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class StateMachineError(RuntimeError):
    def __init__(self, code: TransitionReasonCode, message: str) -> None:
        super().__init__(message)
        self.code = code


WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.ACTIVE: {WorkflowStatus.BLOCKED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.COMPLETED},
    WorkflowStatus.BLOCKED: {WorkflowStatus.ACTIVE, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED, WorkflowStatus.ARCHIVED},
    WorkflowStatus.FAILED: {WorkflowStatus.ACTIVE, WorkflowStatus.ARCHIVED},
    WorkflowStatus.CANCELLED: {WorkflowStatus.ARCHIVED},
    WorkflowStatus.COMPLETED: {WorkflowStatus.ARCHIVED},
    WorkflowStatus.ARCHIVED: set(),
}

STAGE_TRANSITIONS: dict[StageStatus, set[StageStatus]] = {
    StageStatus.PENDING: {StageStatus.RUNNING, StageStatus.SKIPPED, StageStatus.SUPERSEDED},
    StageStatus.RUNNING: {StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.AWAITING_HUMAN, StageStatus.SUPERSEDED},
    StageStatus.COMPLETED: {StageStatus.SUPERSEDED, StageStatus.NEEDS_REVISION},
    StageStatus.FAILED: {StageStatus.RUNNING, StageStatus.SUPERSEDED},
    StageStatus.NEEDS_REVISION: {StageStatus.RUNNING, StageStatus.REJECTED, StageStatus.SUPERSEDED},
    StageStatus.AWAITING_HUMAN: {StageStatus.COMPLETED, StageStatus.NEEDS_REVISION, StageStatus.REJECTED, StageStatus.SUPERSEDED},
    StageStatus.REJECTED: {StageStatus.NEEDS_REVISION, StageStatus.SUPERSEDED},
    StageStatus.SKIPPED: {StageStatus.SUPERSEDED},
    StageStatus.SUPERSEDED: set(),
}

INCOMPLETE_STAGE_STATUSES = {
    StageStatus.PENDING.value,
    StageStatus.RUNNING.value,
    StageStatus.FAILED.value,
    StageStatus.NEEDS_REVISION.value,
    StageStatus.AWAITING_HUMAN.value,
    StageStatus.REJECTED.value,
}

RUNNABLE_RESUME_STATUSES = {
    StageStatus.PENDING.value,
    StageStatus.FAILED.value,
    StageStatus.NEEDS_REVISION.value,
    StageStatus.REJECTED.value,
    StageStatus.SUPERSEDED.value,
}


class WorkflowStateMachine:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transition_workflow(self, request: WorkflowTransitionRequest):
        self._require_identity(request.actor, request.reason, request.actor_type)
        with unit_of_work(self.database) as uow:
            workflow = uow.workflow_runs.get(request.workflow_run_id)
            current = workflow.status
            if request.target_status not in WORKFLOW_TRANSITIONS[current]:
                raise StateMachineError(TransitionReasonCode.INVALID_TRANSITION, f"{current.value}->{request.target_status.value} is not allowed")
            if request.target_status == WorkflowStatus.COMPLETED:
                self._assert_can_complete(uow.conn, workflow.id)
            self._enable_db_guard(uow.conn)
            row = uow.conn.execute(
                """
                UPDATE football_brief.workflow_runs
                SET status = %s,
                    completed_at = CASE WHEN %s IN ('completed','failed','cancelled','archived') THEN now() ELSE completed_at END,
                    failure_reason = CASE WHEN %s = 'failed' THEN %s ELSE failure_reason END
                WHERE id = %s
                RETURNING *
                """,
                (request.target_status.value, request.target_status.value, request.target_status.value, request.reason, workflow.id),
            ).fetchone()
            event = uow.workflow_events.create(
                workflow_run_id=workflow.id,
                stage_execution_id=None,
                event_type="workflow_status_transition",
                from_status=current.value,
                to_status=request.target_status.value,
                actor=request.actor,
                reason=request.reason,
                payload=request.payload,
            )
            return {"workflow": row, "event": event}

    def transition_stage(self, request: StageTransitionRequest):
        self._require_identity(request.actor, request.reason, request.actor_type)
        with unit_of_work(self.database) as uow:
            stage = uow.stage_executions.get(request.stage_execution_id)
            workflow = uow.workflow_runs.get(stage.workflow_run_id)
            if workflow.status not in {WorkflowStatus.ACTIVE, WorkflowStatus.BLOCKED}:
                raise StateMachineError(TransitionReasonCode.WORKFLOW_NOT_ACTIVE, "Workflow is not active")
            current = stage.status
            if request.target_status not in STAGE_TRANSITIONS[current]:
                raise StateMachineError(TransitionReasonCode.INVALID_TRANSITION, f"{current.value}->{request.target_status.value} is not allowed")
            self._enable_db_guard(uow.conn)
            row = self._update_stage(uow.conn, stage.id, request)
            event = uow.workflow_events.create(
                workflow_run_id=stage.workflow_run_id,
                stage_execution_id=stage.id,
                event_type="stage_status_transition",
                from_status=current.value,
                to_status=request.target_status.value,
                actor=request.actor,
                reason=request.reason,
                payload={
                    **request.payload,
                    "output_hash": request.output_hash,
                    "failure_reason": request.failure_reason,
                },
            )
            if request.target_status == StageStatus.COMPLETED and request.output_hash:
                self.invalidate_stale_downstream(stage.id, request.output_hash, actor=request.actor, reason="upstream_output_changed")
            return {"stage": row, "event": event}

    def retry_stage(self, stage_execution_id: UUID, *, actor: str, reason: str):
        self._require_identity(actor, reason, TransitionActorType.OPERATOR)
        with unit_of_work(self.database) as uow:
            old = uow.stage_executions.get(stage_execution_id)
            if old.status not in {StageStatus.FAILED, StageStatus.NEEDS_REVISION, StageStatus.REJECTED, StageStatus.SUPERSEDED}:
                raise StateMachineError(TransitionReasonCode.STAGE_NOT_RETRYABLE, "Stage is not retryable")
            latest_attempt = uow.conn.execute(
                "SELECT COALESCE(MAX(attempt), 0) AS attempt FROM football_brief.stage_executions WHERE workflow_run_id = %s AND stage_name = %s",
                (old.workflow_run_id, old.stage_name),
            ).fetchone()["attempt"]
            new_stage = uow.stage_executions.create(
                StageExecutionCreate(
                    workflow_run_id=old.workflow_run_id,
                    stage_name=old.stage_name,
                    stage_version=old.stage_version,
                    attempt=latest_attempt + 1,
                    idempotency_key=f"{old.id}:retry:{latest_attempt + 1}",
                    input_hash=old.input_hash,
                    model_or_tool=old.model_or_tool,
                    prompt_version=old.prompt_version,
                    timeout_seconds=old.timeout_seconds,
                    estimated_cost_usd=old.estimated_cost_usd,
                    operator=actor,
                )
            )
            uow.workflow_events.create(
                workflow_run_id=old.workflow_run_id,
                stage_execution_id=old.id,
                event_type="stage_retry_created",
                from_status=old.status.value,
                to_status=StageStatus.PENDING.value,
                actor=actor,
                reason=reason,
                payload={"new_stage_execution_id": str(new_stage.id), "new_attempt": new_stage.attempt},
            )
            return new_stage

    def add_dependency(self, data: StageDependencyCreate) -> dict:
        with unit_of_work(self.database) as uow:
            upstream = uow.stage_executions.get(data.upstream_stage_execution_id)
            downstream = uow.stage_executions.get(data.downstream_stage_execution_id)
            expected = data.expected_upstream_output_hash or upstream.output_hash
            if upstream.workflow_run_id != data.workflow_run_id or downstream.workflow_run_id != data.workflow_run_id:
                raise StateMachineError(TransitionReasonCode.INVALID_TRANSITION, "Dependency stages must belong to workflow")
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.stage_dependencies (
                    workflow_run_id, upstream_stage_execution_id, downstream_stage_execution_id,
                    expected_upstream_output_hash, created_by, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (upstream_stage_execution_id, downstream_stage_execution_id)
                DO UPDATE SET expected_upstream_output_hash = EXCLUDED.expected_upstream_output_hash,
                              metadata = EXCLUDED.metadata
                RETURNING *
                """,
                (data.workflow_run_id, data.upstream_stage_execution_id, data.downstream_stage_execution_id, expected, data.created_by, Jsonb(data.metadata)),
            ).fetchone()
            uow.workflow_events.create(
                workflow_run_id=data.workflow_run_id,
                stage_execution_id=data.downstream_stage_execution_id,
                event_type="stage_dependency_recorded",
                actor=data.created_by,
                reason="dependency_graph",
                payload={"upstream_stage_execution_id": str(data.upstream_stage_execution_id), "expected_upstream_output_hash": expected},
            )
            return row

    def invalidate_stale_downstream(self, upstream_stage_execution_id: UUID, new_output_hash: str, *, actor: str, reason: str) -> list[dict]:
        results: list[dict] = []
        with unit_of_work(self.database) as uow:
            rows = uow.conn.execute(
                """
                SELECT downstream.*
                FROM football_brief.stage_dependencies dep
                JOIN football_brief.stage_executions downstream ON downstream.id = dep.downstream_stage_execution_id
                WHERE dep.upstream_stage_execution_id = %s
                  AND dep.expected_upstream_output_hash IS DISTINCT FROM %s
                  AND downstream.status <> 'superseded'
                """,
                (upstream_stage_execution_id, new_output_hash),
            ).fetchall()
            self._enable_db_guard(uow.conn)
            for row in rows:
                updated = uow.conn.execute(
                    "UPDATE football_brief.stage_executions SET status = 'superseded', failure_reason = %s WHERE id = %s RETURNING *",
                    (TransitionReasonCode.STALE_OUTPUT.value, row["id"]),
                ).fetchone()
                event = uow.workflow_events.create(
                    workflow_run_id=row["workflow_run_id"],
                    stage_execution_id=row["id"],
                    event_type="stage_superseded_by_dependency",
                    from_status=row["status"],
                    to_status=StageStatus.SUPERSEDED.value,
                    actor=actor,
                    reason=reason,
                    payload={"upstream_stage_execution_id": str(upstream_stage_execution_id), "new_output_hash": new_output_hash},
                )
                results.append({"stage": updated, "event": event})
        return results

    def resume_plan(self, workflow_run_id: UUID) -> ResumePlan:
        with unit_of_work(self.database) as uow:
            rows = uow.conn.execute(
                "SELECT id, status FROM football_brief.stage_executions WHERE workflow_run_id = %s ORDER BY created_at, attempt",
                (workflow_run_id,),
            ).fetchall()
        runnable = tuple(row["id"] for row in rows if row["status"] in RUNNABLE_RESUME_STATUSES)
        skipped = tuple(row["id"] for row in rows if row["status"] in {StageStatus.COMPLETED.value, StageStatus.SKIPPED.value})
        blocked = tuple(row["id"] for row in rows if row["status"] in {StageStatus.RUNNING.value, StageStatus.AWAITING_HUMAN.value})
        return ResumePlan(workflow_run_id=workflow_run_id, runnable_stage_ids=runnable, skipped_stage_ids=skipped, blocked_stage_ids=blocked)

    @staticmethod
    def _enable_db_guard(conn) -> None:
        conn.execute("SELECT set_config('football_brief.state_machine', 'on', true)")

    @staticmethod
    def _require_identity(actor: str, reason: str, actor_type: TransitionActorType) -> None:
        if actor_type == TransitionActorType.OPERATOR and (not actor.strip() or not reason.strip()):
            raise StateMachineError(TransitionReasonCode.IDENTITY_REQUIRED, "Operator transitions require actor and reason")

    @staticmethod
    def _assert_can_complete(conn, workflow_run_id: UUID) -> None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM football_brief.stage_executions
            WHERE workflow_run_id = %s AND status = ANY(%s)
            """,
            (workflow_run_id, list(INCOMPLETE_STAGE_STATUSES)),
        ).fetchone()
        if row["count"]:
            raise StateMachineError(TransitionReasonCode.REQUIRED_STAGE_NOT_COMPLETE, "Workflow has incomplete required stages")

    @staticmethod
    def _update_stage(conn, stage_id: UUID, request: StageTransitionRequest) -> dict:
        return conn.execute(
            """
            UPDATE football_brief.stage_executions
            SET status = %s,
                started_at = CASE WHEN %s = 'running' THEN COALESCE(started_at, now()) ELSE started_at END,
                completed_at = CASE WHEN %s IN ('completed','failed','skipped','rejected','superseded') THEN now() ELSE completed_at END,
                output_hash = COALESCE(%s, output_hash),
                failure_reason = COALESCE(%s, failure_reason),
                output = COALESCE(%s, output)
            WHERE id = %s
            RETURNING *
            """,
            (
                request.target_status.value,
                request.target_status.value,
                request.target_status.value,
                request.output_hash,
                request.failure_reason,
                Jsonb(request.output) if request.output is not None else None,
                stage_id,
            ),
        ).fetchone()
