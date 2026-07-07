from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p6-step-03.md")


def test_p6_observability_contract_documents_required_log_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Structured log fields",
        "timestamp",
        "level",
        "event name",
        "service name",
        "runtime environment",
        "request id",
        "workflow id when available",
        "operator id when available",
        "route name when available",
        "status code when available",
        "outcome",
        "duration milliseconds when available",
    ]

    for term in required_terms:
        assert term in content


def test_p6_observability_contract_documents_identifiers_and_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Request and workflow identifiers",
        "Every inbound API request should carry or receive a request id.",
        "Operator action logging",
        "action name",
        "resource id when available",
        "failure reason when the action fails",
        "must not imply automatic approval",
    ]

    for term in required_terms:
        assert term in content


def test_p6_observability_contract_documents_errors_metrics_and_alerts() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Error logging expectations",
        "safe error summary",
        "Safe operational metrics",
        "request count by route",
        "response count by status code family",
        "request duration by route",
        "queue item count",
        "workflow run count by status",
        "approval action count by action and outcome",
        "bounded cardinality",
        "Alert candidates",
        "healthcheck failure",
        "repeated 5xx responses",
        "database connection failures",
        "migration readiness failures",
    ]

    for term in required_terms:
        assert term in content


def test_p6_observability_contract_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Do not log detailed runtime values.",
        "Do not log full request bodies by default.",
        "Do not add a collector in this step.",
        "Do not add a metrics service in this step.",
        "Do not add publishing.",
        "Do not add scheduling.",
        "Do not add rendering.",
        "Do not add external export.",
    ]

    for term in required_terms:
        assert term in content
