from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p18-step-04.md")


def test_p18_support_playbook_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-03.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p16-readiness-report.md",
    ]:
        assert term in content


def test_p18_support_playbook_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This support playbook is documentation-only.",
        "create a live support queue",
        "grant support access",
        "approve production launch",
        "schedule production launch",
        "execute support automation",
        "send customer communication",
        "publish support material",
        "render support material",
        "export support evidence",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p18_support_playbook_documents_categories_severity_and_triage_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "access or permission issue",
        "workflow or CI issue",
        "release readiness question",
        "observability or metric question",
        "alert or incident signal",
        "documentation gap",
        "operator handover question",
        "customer-impact concern",
        "evidence handling concern",
        "recurring support pattern",
        "blocked by guardrail",
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        "customer impact",
        "release impact",
        "operational impact",
        "evidence sensitivity",
        "incident recurrence",
        "rollback relevance",
        "support case identifier",
        "category",
        "severity",
        "reported by",
        "support owner",
        "operator owner",
        "incident owner when applicable",
        "release owner when applicable",
        "evidence source",
        "customer impact status",
        "action route",
        "escalation route",
        "closure criteria",
    ]:
        assert term in content


def test_p18_support_playbook_documents_cases_process_escalation_and_operator_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "failed exact-head CI",
        "workflow cannot start",
        "missing issue owner",
        "missing PR reviewer",
        "unclear issue scope",
        "expanded PR scope",
        "release approval question",
        "blackout window conflict",
        "alert noise question",
        "repeated incident signal",
        "support volume spike",
        "rollback trigger question",
        "documentation freshness gap",
        "evidence sensitivity concern",
        "restricted value found in notes",
        "classify support case category",
        "assign severity",
        "assign support owner",
        "identify operator owner",
        "identify incident owner when applicable",
        "identify release owner when applicable",
        "classify evidence sensitivity",
        "determine customer impact status",
        "choose action route",
        "severity is high",
        "severity is critical",
        "incident signal appears",
        "customer impact is suspected",
        "rollback trigger is suggested",
        "release decision is requested",
        "workflow gate bypass is requested",
        "gather summarized support context",
        "link issue or PR references",
        "capture CI run identifiers",
        "route case to support owner",
        "route incident signal to incident owner",
        "route release question to release owner",
        "request evidence replacement",
        "close high or critical cases without owner review",
    ]:
        assert term in content


def test_p18_support_playbook_documents_evidence_closure_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized support notes",
        "summarized operator notes",
        "summarized incident notes",
        "summarized alert notes",
        "summarized customer-impact notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered support materials",
        "scheduled support outputs",
        "category is recorded",
        "severity is recorded",
        "support owner is recorded",
        "action owner is recorded when action is required",
        "restricted evidence is removed or replaced",
        "follow-up issue is created when implementation is required",
        "support owner is missing",
        "action owner is missing for required action",
        "severity is high or critical without escalation",
        "customer impact is suspected without owner review",
        "incident signal has no incident owner",
        "rollback trigger has no release owner",
        "release decision is implied",
        "production launch is implied",
        "customer data export is requested",
        "external export is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
