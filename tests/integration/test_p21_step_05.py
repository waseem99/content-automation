from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p21-step-05.md")


def test_p21_escalation_routing_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p21-step-01.md",
        "docs/operations/p21-step-02.md",
        "docs/operations/p21-step-04.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-04.md",
    ]:
        assert term in content


def test_p21_escalation_routing_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This escalation drill and contact routing plan is documentation-only.",
        "notify external contacts",
        "send customer communication",
        "schedule meetings",
        "schedule drill automation",
        "execute live escalation",
        "approve production launch",
        "bypass workflow gates",
        "publish routing evidence",
        "render routing evidence",
        "export restricted evidence",
    ]:
        assert term in content


def test_p21_escalation_routing_documents_roles_matrix_prompts_and_placeholders() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "facilitator",
        "operator owner",
        "support owner",
        "incident owner",
        "release owner",
        "evidence owner",
        "documentation owner",
        "reviewer",
        "observer",
        "exact-head CI failure",
        "workflow cannot start",
        "support case suggests customer impact",
        "security incident signal",
        "restricted evidence suspected",
        "rollback decision question",
        "restore decision question",
        "blackout window conflict",
        "workflow gate bypass request",
        "Which primary route applies?",
        "Which secondary route applies?",
        "Which evidence is safe to retain?",
        "Is rollback or restore explicitly approved?",
        "role placeholder",
        "team placeholder",
        "contact route placeholder",
        "response window placeholder",
        "backup owner placeholder",
        "Do not record real phone numbers",
    ]:
        assert term in content


def test_p21_escalation_routing_documents_response_evidence_results_followups_and_stops() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "select the correct primary route",
        "select the correct secondary route when required",
        "identify the response owner",
        "classify evidence sensitivity",
        "avoid external notification",
        "avoid implied live escalation",
        "escalation drill identifier",
        "primary route",
        "secondary route",
        "expected response summary",
        "actual response summary",
        "escalation result",
        "pass with notes",
        "partial pass",
        "follow-up required",
        "update recovery drill plan",
        "update tabletop exercise",
        "update operator failure-mode checklist",
        "update security incident playbook",
        "update audit trail evidence",
        "create implementation issue",
        "summarized routing note",
        "real phone numbers",
        "private email addresses",
        "customer identifiers",
        "real external contact is recorded",
        "external notification is implied",
        "live escalation is implied",
        "rollback is implied without explicit approval",
        "restore is implied without explicit approval",
    ]:
        assert term in content


def test_p21_escalation_routing_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "No automatic approval.",
        "No automatic release.",
        "No automatic escalation.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
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
