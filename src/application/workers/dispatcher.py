from __future__ import annotations

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from src.application.state_machine import WorkflowStateMachine
from src.application.workers.hashing import output_hash, worker_idempotency_key, worker_input_hash
from src.application.workers.models import (
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerFailure,
    WorkerFailureClass,
    WorkerHandlerResult,
    WorkerOutcome,
)
from src.application.workers.registry import WorkerRegistry
from src.domain.workflow_models import StageExecution, StageExecutionCreate
from src.domain.workflow_state_models import StageTransitionRequest, TransitionActorType
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class WorkerDispatcher:
    def __init__(self, *, database: Database, registry: WorkerRegistry, state_machine: WorkflowStateMachine | None = None) -> None:
        self.database = database
        self.registry = registry
        self.state_machine = state_machine or WorkflowStateMachine(database)

    def execute(self, request: WorkerExecutionRequest) -> WorkerExecutionResult:
        registered = self.registry.get(request.worker_name, request.worker_version)
        definition = registered.definition
        input_hash = worker_input_hash(definition, request.input_payload)
        idempotency_key = worker_idempotency_key(definition, request.input_payload)
        existing = self._get_stage_by_idempotency(idempotency_key)
        if existing is not None:
            return self._reuse_or_report_existing(existing, idempotency_key, input_hash, request.actor)

        stage = self._create_stage(request, definition, idempotency_key, input_hash)
        self.state_machine.transition_stage(
            StageTransitionRequest(
                stage_execution_id=stage.id,
                target_status=StageStatus.RUNNING,
                actor=request.actor,
                actor_type=TransitionActorType.WORKER,
                reason="worker_started",
                payload={"worker": definition.name, "version": definition.version},
            )
        )
        try:
            handler_result = registered.handler(request.input_payload)
        except WorkerFailure as exc:
            return self._handle_failure(stage.id, idempotency_key, input_hash, exc.failure_class, exc.message, request.actor)
        except Exception as exc:
            return self._handle_failure(stage.id, idempotency_key, input_hash, WorkerFailureClass.RETRYABLE, str(exc), request.actor)

        if not isinstance(handler_result, WorkerHandlerResult):
            try:
                handler_result = WorkerHandlerResult.model_validate(handler_result)
            except Exception as exc:
                return self._handle_failure(
                    stage.id,
                    idempotency_key,
                    input_hash,
                    WorkerFailureClass.SCHEMA_VALIDATION_FAILED,
                    str(exc),
                    request.actor,
                )
        computed_output_hash = output_hash(handler_result.output)
        self._record_provider_call_if_requested(request, stage.id, idempotency_key, input_hash, computed_output_hash, handler_result)
        self.state_machine.transition_stage(
            StageTransitionRequest(
                stage_execution_id=stage.id,
                target_status=StageStatus.COMPLETED,
                actor=request.actor,
                actor_type=TransitionActorType.WORKER,
                reason="worker_succeeded",
                output_hash=computed_output_hash,
                output=handler_result.output,
                payload={"worker": definition.name, "version": definition.version},
            )
        )
        self._event(stage.workflow_run_id, stage.id, "worker_succeeded", request.actor, "completed", {"output_hash": computed_output_hash})
        return WorkerExecutionResult(
            outcome=WorkerOutcome.SUCCEEDED,
            stage_execution_id=stage.id,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            output_hash=computed_output_hash,
            output=handler_result.output,
            attempt=stage.attempt,
        )

    def _create_stage(self, request: WorkerExecutionRequest, definition, idempotency_key: str, input_hash: str) -> StageExecution:
        try:
            with unit_of_work(self.database) as uow:
                return uow.stage_executions.create(
                    StageExecutionCreate(
                        workflow_run_id=request.workflow_run_id,
                        stage_name=request.stage_name or definition.name,
                        stage_version=definition.version,
                        idempotency_key=idempotency_key,
                        input_hash=input_hash,
                        model_or_tool=definition.name,
                        prompt_version=definition.version,
                        timeout_seconds=definition.timeout_seconds,
                        estimated_cost_usd=definition.estimated_cost_usd,
                        operator=request.actor,
                    )
                )
        except UniqueViolation:
            existing = self._get_stage_by_idempotency(idempotency_key)
            if existing is not None:
                return existing
            raise

    def _reuse_or_report_existing(self, stage: StageExecution, idempotency_key: str, input_hash: str, actor: str) -> WorkerExecutionResult:
        if stage.status == StageStatus.COMPLETED and stage.output_hash:
            self._event(stage.workflow_run_id, stage.id, "worker_result_reused", actor, "idempotency_hit", {"output_hash": stage.output_hash})
            return WorkerExecutionResult(
                outcome=WorkerOutcome.REUSED,
                stage_execution_id=stage.id,
                idempotency_key=idempotency_key,
                input_hash=input_hash,
                output_hash=stage.output_hash,
                output=stage.output,
                attempt=stage.attempt,
                reused=True,
            )
        if stage.status == StageStatus.RUNNING:
            return WorkerExecutionResult(
                outcome=WorkerOutcome.ALREADY_RUNNING,
                stage_execution_id=stage.id,
                idempotency_key=idempotency_key,
                input_hash=input_hash,
                attempt=stage.attempt,
            )
        return WorkerExecutionResult(
            outcome=WorkerOutcome.FAILED,
            stage_execution_id=stage.id,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            attempt=stage.attempt,
            failure_reason=stage.failure_reason,
        )

    def _handle_failure(self, stage_id, idempotency_key: str, input_hash: str, failure_class: WorkerFailureClass, message: str, actor: str) -> WorkerExecutionResult:
        target = StageStatus.AWAITING_HUMAN if failure_class == WorkerFailureClass.HUMAN_REVIEW_REQUIRED else StageStatus.FAILED
        self.state_machine.transition_stage(
            StageTransitionRequest(
                stage_execution_id=stage_id,
                target_status=target,
                actor=actor,
                actor_type=TransitionActorType.WORKER,
                reason=failure_class.value,
                failure_reason=message,
                payload={"failure_class": failure_class.value},
            )
        )
        return WorkerExecutionResult(
            outcome=WorkerOutcome.HUMAN_REVIEW_REQUIRED if target == StageStatus.AWAITING_HUMAN else WorkerOutcome.FAILED,
            stage_execution_id=stage_id,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            failure_class=failure_class,
            failure_reason=message,
        )

    def _get_stage_by_idempotency(self, idempotency_key: str) -> StageExecution | None:
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute(
                "SELECT * FROM football_brief.stage_executions WHERE idempotency_key = %s",
                (idempotency_key,),
            ).fetchone()
            return StageExecution.model_validate(row) if row else None

    def _record_provider_call_if_requested(self, request: WorkerExecutionRequest, stage_id, idempotency_key: str, input_hash: str, response_hash: str, result: WorkerHandlerResult) -> None:
        if not request.provider or not request.operation:
            return
        with unit_of_work(self.database) as uow:
            uow.conn.execute(
                """
                INSERT INTO football_brief.provider_calls (
                    stage_execution_id, provider, operation, provider_request_id,
                    idempotency_key, status, request_fingerprint, response_fingerprint,
                    units, unit_name, cost_usd, completed_at, metadata
                ) VALUES (%s, %s, %s, %s, %s, 'succeeded', %s, %s, %s, %s, %s, now(), %s)
                ON CONFLICT (provider, idempotency_key) DO NOTHING
                """,
                (
                    stage_id,
                    request.provider,
                    request.operation,
                    result.provider_request_id or request.provider_request_id,
                    idempotency_key,
                    input_hash,
                    response_hash,
                    result.units,
                    result.unit_name,
                    result.cost_usd,
                    Jsonb(result.metadata),
                ),
            )

    def _event(self, workflow_run_id, stage_id, event_type: str, actor: str, reason: str, payload: dict) -> None:
        with unit_of_work(self.database) as uow:
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=stage_id,
                event_type=event_type,
                actor=actor,
                reason=reason,
                payload=payload,
            )
