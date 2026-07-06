from uuid import uuid4

from src.application.observability.logging import StructuredLogContext, log_event
from src.application.observability.metrics import MetricsRegistry
from src.application.observability.redaction import MASK, redact_value
from src.application.secrets.provider import EnvSecretProvider, RuntimeEnvironment, SecretRequirement, SecretValidator


def test_production_rejects_env_secret_provider_for_required_secret(monkeypatch):
    monkeypatch.setenv("DEMO_SECRET", "value")
    report = SecretValidator(EnvSecretProvider(), environment=RuntimeEnvironment.PRODUCTION).validate((SecretRequirement(name="DEMO_SECRET"),))
    assert report.ok is False
    assert report.missing == ("DEMO_SECRET",)


def test_local_secret_validation_passes_when_present(monkeypatch):
    monkeypatch.setenv("DEMO_SECRET", "value")
    report = SecretValidator(EnvSecretProvider(), environment=RuntimeEnvironment.LOCAL).validate((SecretRequirement(name="DEMO_SECRET"),))
    assert report.ok is True


def test_redaction_masks_sensitive_keys_and_values():
    cleaned = redact_value({"authorization": "Bearer abcdef12345", "nested": {"note": "sk-123456789012345"}})
    assert cleaned["authorization"] == MASK
    assert cleaned["nested"]["note"] == MASK


def test_structured_log_has_correlation_and_masks_payload():
    workflow_id = uuid4()
    event = log_event(
        "provider_started",
        context=StructuredLogContext(workflow_run_id=workflow_id, provider="demo"),
        payload={"authorization": "Bearer abcdef12345", "safe": "ok"},
    ).as_dict()
    assert event["context"]["workflow_run_id"] == str(workflow_id)
    assert event["payload"]["authorization"] == MASK
    assert event["payload"]["safe"] == "ok"


def test_metrics_registry_records_counters_and_totals():
    metrics = MetricsRegistry()
    metrics.increment("stage.failures")
    metrics.observe("provider.cost", "0.25")
    snapshot = metrics.snapshot()
    assert snapshot.counters["stage.failures"] == 1
    assert snapshot.totals["provider.cost"] == "0.25"
