from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p21-step-04.md")


def test_p21_operator_failure_modes_reference_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p21-step-01.md",
        "docs/operations/p21-step-02.md",
        "docs/operations/p21-step-03.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-readiness-report.md",
    ]:
        assert term in content


def test_p21_operator_failure_modes_are_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This operator failure-mode checklist is documentation-only.",
        "execute live operator actions",
        "change production configuration",
        "approve production launch",
        "schedule operational work",
        "notify external contacts",
        "bypass workflow gates",
        "merge changes",
        "publish checklist evidence",
        "render checklist evidence",
        "export restricted evidence",
    ]:
        assert term in content


def test_p21_operator_failure_modes_document_modes_signals_routes_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "exact-head CI failure",
        "workflow cannot start",
        "issue owner missing",
        "reviewer missing",
        "evidence source missing",
        "support case without owner",
        "incident signal without owner",
        "rollback decision without approval",
        "restore decision without approval",
        "blackout conflict",
        "failed CI run",
        "missing run identifier",
        "open PR without owner",
        "support note requiring escalation",
        "restricted value suspected",
        "customer impact suspected",
        "stale runbook detected",
        "request missing owner",
        "request reviewer",
        "create implementation issue",
        "escalate to support owner",
        "escalate to incident owner",
        "escalate to release owner",
        "block by guardrail",
        "checklist item identifier",
        "failure mode",
        "detection signal",
        "safe response route",
        "pass/fail status",
    ]:
        assert term in content


def test_p21_operator_failure_modes_document_statuses_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "pass with notes",
        "needs owner",
        "needs reviewer",
        "needs evidence",
        "needs escalation",
        "issue or PR reference",
        "CI run identifier",
        "summarized operator note",
        "summarized support note",
        "summarized incident note",
        "secret values",
        "private runtime values",
        "customer data exports",
        "external package exports",
        "checklist item identifier is missing",
        "safe response route is missing",
        "live operator action is implied",
        "production change is implied",
        "external notification is implied",
        "No automatic approval.",
        "No automatic release.",
        "No automatic operator action.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
