import pytest

from src.application.workers.models import WorkerDefinition, WorkerHandlerResult
from src.application.workers.registry import WorkerRegistry, WorkerRegistryError


def handler(data):
    return WorkerHandlerResult(output={"ok": data.get("ok", True)})


def definition():
    return WorkerDefinition(
        name="demo_worker",
        version="1",
        input_schema_name="DemoInput",
        input_schema_version="1",
        output_schema_name="DemoOutput",
        output_schema_version="1",
    )


def test_registry_rejects_duplicate_definition():
    registry = WorkerRegistry()
    worker = definition()
    registry.register(worker, handler)
    with pytest.raises(WorkerRegistryError):
        registry.register(worker, handler)
