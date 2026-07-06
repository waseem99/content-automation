from __future__ import annotations

from decimal import Decimal

from src.application.budget.service import BudgetControlService
from src.application.budget.worker_dispatcher import BudgetedWorkerDispatcher
from src.application.workers.models import WorkerHandlerResult
from src.application.workers.registry import WorkerRegistry
from src.domain.budget_models import BudgetLimit
from tests.integration.worker_support import definition


class FixedWorker:
    def __init__(self):
        self.calls = 0

    def __call__(self, payload):
        self.calls += 1
        return WorkerHandlerResult(output={"value": payload.get("value", "ok")}, units=Decimal("1"), metadata={"safe": "ok"})


def budgeted_dispatcher(database, *, limits: BudgetLimit | None = None, handler=None, worker_definition=None):
    registry = WorkerRegistry()
    worker_definition = worker_definition or definition()
    handler = handler or FixedWorker()
    registry.register(worker_definition, handler)
    budget = BudgetControlService(database=database, limits=limits or BudgetLimit())
    return BudgetedWorkerDispatcher(database=database, registry=registry, budget_control=budget), budget, handler
