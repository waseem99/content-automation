from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p21-step-02.md")


def test_p21_tabletop_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p21-step-01.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p20-readiness-report.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p16-step-03.md",
    ]:
        assert term in content


def test_p21_tabletop_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This tabletop exercise is documentation-only.",
        "create a live incident",
        "execute containment actions",
        "rotate secrets",
        "notify external contacts",
        "send customer communication",
        "schedule external meetings",
        "approve production launch",
        "bypass workflow gates",
        "publish tabletop evidence",
        "export restricted evidence",
    ]:
        assert term in content


def test_p21_tabletop_documents_roles_scenarios_decisions_and_prompts() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "facilitator",
        "incident owner",
        "operator owner",
        "support owner",
        "release owner",
        "evidence owner",
        "reviewer",
        "observer",
        "suspected secret exposure",
        "confirmed restricted evidence in notes",
        "support case suggests customer impact",
        "high-severity dependency finding",
        "workflow cannot start",
        "exact-head CI fails",
        "rollback decision question appears",
        "missing incident owner",
        "workflow gate bypass is requested",
        "incident category",
        "severity level",
        "containment route",
        "customer-impact status",
        "follow-up issue requirement",
        "Which evidence is safe to retain?",
        "Which escalation route applies?",
        "What would block closure?",
    ]:
        assert term in content


def test_p21_tabletop_documents_evidence_scoring_followup_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "tabletop record identifier",
        "prompt set",
        "expected decision",
        "actual decision summary",
        "scoring result",
        "reviewer notes",
        "pass with notes",
        "partial pass",
        "blocked by guardrail",
        "follow-up required",
        "update recovery drill plan",
        "update security incident playbook",
        "update support playbook",
        "update audit trail evidence",
        "create implementation issue",
        "escalate to incident owner",
        "escalate to evidence owner",
        "summarized tabletop note",
        "summarized decision note",
        "secret values",
        "private runtime values",
        "customer data exports",
        "external package exports",
        "scenario name is missing",
        "live incident action is implied",
        "external communication is implied",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
