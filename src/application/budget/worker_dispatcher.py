from __future__ import annotations

from src.application.budget.service import BudgetApprovalRequired, BudgetCircuitOpen, BudgetControlService
from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerExecutionRequest, WorkerExecutionResult, WorkerFailureClass, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.domain.budget_models import BudgetCheckRequest
from src.infrastructure.database.connection import Database


class BudgetedWorkerDispatcher:
    def __init__(self, *, database: Database, registry: WorkerRegistry, budget_control: BudgetControlService) -> None:
        self.database = database
        self.registry = registry
        self.budget_control = budget_control
        self.worker_dispatcher = WorkerDispatcher(database=database, registry=registry)

    def execute(self, request: WorkerExecutionRequest) -> WorkerExecutionResult:
        if request.provider and request.operation:
            try:
                self.budget_control.check_pre_call_budget(
                    BudgetCheckRequest(
                        workflow_run_id=request.workflow_run_id,
                        stage_execution_id=None,
                        provider=request.provider,
                        operation=request.operation,
                        model_id=request.provider_model_id,
                        units=request.provider_units,
                        actor=request.actor,
                    )
                )
            except BudgetApprovalRequired as exc:
                return WorkerExecutionResult(
                    outcome=WorkerOutcome.HUMAN_REVIEW_REQUIRED,
                    idempotency_key="budget-review-required",
                    input_hash="0" * 64,
                    failure_class=WorkerFailureClass.HUMAN_REVIEW_REQUIRED,
                    failure_reason=str(exc),
                )
            except BudgetCircuitOpen as exc:
                return WorkerExecutionResult(
                    outcome=WorkerOutcome.FAILED,
                    idempotency_key="budget-stopped",
                    input_hash="0" * 64,
                    failure_class=WorkerFailureClass.NON_RETRYABLE,
                    failure_reason=str(exc),
                )

        provider = request.provider
        operation = request.operation
        model_id = request.provider_model_id
        units = request.provider_units
        provider_request_id = request.provider_request_id
        run_request = request.model_copy(update={"provider": None, "operation": None, "provider_request_id": None})
        result = self.worker_dispatcher.execute(run_request)
        if result.outcome == WorkerOutcome.SUCCEEDED and provider and operation and result.stage_execution_id and result.output_hash:
            self.budget_control.record_successful_call(
                workflow_run_id=request.workflow_run_id,
                stage_execution_id=result.stage_execution_id,
                provider=provider,
                operation=operation,
                model_id=model_id,
                provider_request_id=provider_request_id,
                idempotency_key=result.idempotency_key,
                request_fingerprint=result.input_hash,
                response_fingerprint=result.output_hash,
                units=units,
                metadata={"worker_name": request.worker_name, "worker_version": request.worker_version},
            )
        return result
