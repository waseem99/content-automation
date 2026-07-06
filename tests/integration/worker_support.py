from __future__ import annotations

from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerHandlerResult
from src.application.workers.registry import WorkerRegistry


class CountingWorker:
    def __init__(self):
        self.calls = 0

    def __call__(self, payload):
        self.calls += 1
        return WorkerHandlerResult(output={"value": payload.get("value", "ok"), "calls": self.calls})


def definition(name="demo_worker", version="1"):
    return WorkerDefinition(
        name=name,
        version=version,
        input_schema_name="DemoInput",
        input_schema_version="1",
        output_schema_name="DemoOutput",
        output_schema_version="1",
        idempotency_fields=("value",),
    )


def dispatcher(database, handler=None, worker_definition=None):
    registry = WorkerRegistry()
    worker_definition = worker_definition or definition()
    handler = handler or CountingWorker()
    registry.register(worker_definition, handler)
    return WorkerDispatcher(database=database, registry=registry), handler
