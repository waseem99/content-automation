from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from src.application.budget.metadata_filter import scrub_metadata
from src.application.budget.pricing import PricingCatalog, PricingNotFound, default_pricing_catalog
from src.domain.budget_models import (
    BudgetCheckRequest,
    BudgetCheckResult,
    BudgetDecision,
    BudgetLimit,
    BudgetStopReason,
    CostEntryCreate,
    CostReconciliationReport,
    ProviderCall,
    ProviderCallCreate,
    ProviderCallStatus,
)
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_budget import CostEntryRepository, ProviderCallRepository
from src.infrastructure.database.uow import unit_of_work


class BudgetControlError(RuntimeError):
    pass


class BudgetCircuitOpen(BudgetControlError):
    def __init__(self, result: BudgetCheckResult) -> None:
        super().__init__(",".join(reason.value for reason in result.reasons))
        self.result = result


class BudgetApprovalRequired(BudgetControlError):
    def __init__(self, result: BudgetCheckResult) -> None:
        super().__init__(BudgetStopReason.PREMIUM_REQUIRES_APPROVAL.value)
        self.result = result


class BudgetControlService:
    policy_version = "budget-policy-v1"

    def __init__(self, *, database: Database, catalog: PricingCatalog | None = None, limits: BudgetLimit | None = None) -> None:
        self.database = database
        self.catalog = catalog or default_pricing_catalog()
        self.limits = limits or BudgetLimit()

    def check_pre_call_budget(self, request: BudgetCheckRequest) -> BudgetCheckResult:
        try:
            estimate, pricing = self.catalog.estimate(
                provider=request.provider,
                operation=request.operation,
                model_id=request.model_id,
                units=request.units,
            )
        except PricingNotFound:
            result = BudgetCheckResult(
                decision=BudgetDecision.STOP,
                estimated_cost_usd=Decimal("0.0000"),
                reasons=(BudgetStopReason.UNKNOWN_PRICING,),
            )
            self._event(request.workflow_run_id, request.stage_execution_id, "budget_stopped", request.actor, result)
            raise BudgetCircuitOpen(result)

        reasons: list[BudgetStopReason] = []
        with unit_of_work(self.database) as uow:
            workflow = uow.workflow_runs.get(request.workflow_run_id)
            stage = uow.stage_executions.get(request.stage_execution_id) if request.stage_execution_id else None
            provider_spend = self._provider_spend(uow.conn, request.provider, request.workflow_run_id)
            daily_spend = self._daily_spend(uow.conn, request.today or date.today())

        workflow_limit = self.limits.workflow_limit_usd if self.limits.workflow_limit_usd is not None else workflow.approved_budget_usd
        if workflow_limit is not None and workflow.actual_cost_usd + estimate > workflow_limit:
            reasons.append(BudgetStopReason.WORKFLOW_LIMIT)
        if stage and self.limits.stage_limit_usd is not None and stage.actual_cost_usd + estimate > self.limits.stage_limit_usd:
            reasons.append(BudgetStopReason.STAGE_LIMIT)
        if self.limits.provider_limit_usd is not None and provider_spend + estimate > self.limits.provider_limit_usd:
            reasons.append(BudgetStopReason.PROVIDER_LIMIT)
        if self.limits.daily_limit_usd is not None and daily_spend + estimate > self.limits.daily_limit_usd:
            reasons.append(BudgetStopReason.DAILY_LIMIT)

        if reasons:
            result = BudgetCheckResult(decision=BudgetDecision.STOP, estimated_cost_usd=estimate, reasons=tuple(reasons), pricing_profile=pricing.profile_version)
            self._event(request.workflow_run_id, request.stage_execution_id, "budget_stopped", request.actor, result)
            raise BudgetCircuitOpen(result)

        if pricing.premium or (self.limits.premium_threshold_usd is not None and estimate >= self.limits.premium_threshold_usd):
            if self.limits.require_approval_for_premium:
                result = BudgetCheckResult(
                    decision=BudgetDecision.NEEDS_APPROVAL,
                    estimated_cost_usd=estimate,
                    reasons=(BudgetStopReason.PREMIUM_REQUIRES_APPROVAL,),
                    pricing_profile=pricing.profile_version,
                    requires_review=True,
                )
                self._event(request.workflow_run_id, request.stage_execution_id, "budget_review_required", request.actor, result)
                raise BudgetApprovalRequired(result)

        return BudgetCheckResult(decision=BudgetDecision.ALLOW, estimated_cost_usd=estimate, pricing_profile=pricing.profile_version)

    def record_successful_call(
        self,
        *,
        workflow_run_id: UUID,
        stage_execution_id: UUID,
        provider: str,
        operation: str,
        model_id: str | None,
        provider_request_id: str | None,
        idempotency_key: str,
        request_fingerprint: str,
        response_fingerprint: str,
        units: Decimal,
        metadata: dict,
    ) -> ProviderCall:
        estimate, pricing = self.catalog.estimate(provider=provider, operation=operation, model_id=model_id, units=units)
        clean_metadata = scrub_metadata(metadata)
        with unit_of_work(self.database) as uow:
            provider_call = ProviderCallRepository(uow.conn).create(
                ProviderCallCreate(
                    stage_execution_id=stage_execution_id,
                    provider=provider,
                    operation=operation,
                    provider_request_id=provider_request_id,
                    idempotency_key=idempotency_key,
                    status=ProviderCallStatus.SUCCEEDED,
                    request_fingerprint=request_fingerprint,
                    response_fingerprint=response_fingerprint,
                    units=units,
                    unit_name=pricing.unit_name,
                    cost_usd=estimate,
                    model_id=model_id,
                    pricing_profile=pricing.profile_version,
                    budget_policy_version=self.policy_version,
                    metadata=clean_metadata,
                )
            )
            CostEntryRepository(uow.conn).create(
                CostEntryCreate(
                    workflow_run_id=workflow_run_id,
                    stage_execution_id=stage_execution_id,
                    provider_call_id=provider_call.id,
                    category="provider_call",
                    amount_usd=estimate,
                    quantity=units,
                    unit_name=pricing.unit_name,
                    pricing_profile=pricing.profile_version,
                    reconciliation_key=f"provider:{provider_call.id}",
                    metadata={"provider": provider, "operation": operation, "model_id": model_id},
                )
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=stage_execution_id,
                event_type="provider_cost_recorded",
                actor="budget-control",
                reason="provider_call",
                payload={"provider_call_id": str(provider_call.id), "amount_usd": str(estimate), "pricing_profile": pricing.profile_version},
            )
            return provider_call

    def reconcile_workflow_cost(self, workflow_run_id: UUID) -> CostReconciliationReport:
        with unit_of_work(self.database) as uow:
            cost_total = Decimal(CostEntryRepository(uow.conn).sum_for_workflow(workflow_run_id))
            provider_total = Decimal(ProviderCallRepository(uow.conn).sum_for_workflow(workflow_run_id))
            workflow = uow.workflow_runs.get(workflow_run_id)
        return CostReconciliationReport(
            workflow_run_id=workflow_run_id,
            cost_entry_total_usd=cost_total,
            provider_call_total_usd=provider_total,
            workflow_actual_cost_usd=workflow.actual_cost_usd,
            matched=workflow.actual_cost_usd == cost_total,
            provider_mismatch_usd=(provider_total - cost_total).quantize(Decimal("0.0001")),
        )

    @staticmethod
    def _provider_spend(conn, provider: str, workflow_run_id: UUID) -> Decimal:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(provider_calls.cost_usd), 0)::text AS total
            FROM football_brief.provider_calls provider_calls
            JOIN football_brief.stage_executions stage ON stage.id = provider_calls.stage_execution_id
            WHERE provider_calls.provider = %s
              AND stage.workflow_run_id = %s
              AND provider_calls.status = 'succeeded'
            """,
            (provider, workflow_run_id),
        ).fetchone()
        return Decimal(row["total"])

    @staticmethod
    def _daily_spend(conn, day: date) -> Decimal:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0)::text AS total FROM football_brief.provider_calls WHERE started_at::date = %s AND status = 'succeeded'",
            (day,),
        ).fetchone()
        return Decimal(row["total"])

    def _event(self, workflow_run_id: UUID, stage_execution_id: UUID | None, event_type: str, actor: str, result: BudgetCheckResult) -> None:
        with unit_of_work(self.database) as uow:
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=stage_execution_id,
                event_type=event_type,
                actor=actor,
                reason=",".join(reason.value for reason in result.reasons),
                payload={
                    "decision": result.decision.value,
                    "estimated_cost_usd": str(result.estimated_cost_usd),
                    "reasons": [reason.value for reason in result.reasons],
                    "pricing_profile": result.pricing_profile,
                },
            )
