from src.application.workers.hashing import worker_idempotency_key, worker_input_hash
from src.application.workers.models import WorkerDefinition


def _definition(version="1"):
    return WorkerDefinition(
        name="demo_worker",
        version=version,
        input_schema_name="DemoInput",
        input_schema_version="1",
        output_schema_name="DemoOutput",
        output_schema_version="1",
        idempotency_fields=("asset_id", "language"),
    )


def test_same_selected_input_produces_same_key():
    first = {"asset_id": "a1", "language": "en", "unused": "one"}
    second = {"language": "en", "asset_id": "a1", "unused": "two"}
    assert worker_input_hash(_definition(), first) == worker_input_hash(_definition(), second)
    assert worker_idempotency_key(_definition(), first) == worker_idempotency_key(_definition(), second)


def test_worker_version_changes_key():
    payload = {"asset_id": "a1", "language": "en"}
    assert worker_idempotency_key(_definition("1"), payload) != worker_idempotency_key(_definition("2"), payload)
