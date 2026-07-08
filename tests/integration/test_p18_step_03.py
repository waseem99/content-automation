from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p18-step-03.md")


def test_p18_onboarding_checklist_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p15-readiness-report.md",
    ]:
        assert term in content


def test_p18_onboarding_checklist_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This checklist is documentation-only.",
        "grant production access",
        "approve production launch",
        "schedule production launch",
        "execute release activities",
        "replace role-based procedures",
        "replace support escalation",
        "publish onboarding material",
        "render training material",
        "export onboarding evidence",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p18_onboarding_checklist_documents_sequence_reading_and_questions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "confirm assigned role",
        "review operator handover guide",
        "review role-based procedure",
        "review release readiness context",
        "review observability context",
        "review evidence handling rules",
        "complete validation questions",
        "complete escalation readiness check",
        "complete manual role sign-off",
        "record evidence-safe onboarding completion",
        "P18 operator handover guide",
        "P18 role-based operating procedures",
        "P17 release readiness report",
        "P17 release decision pack",
        "P17 production release checklist",
        "P17 dry-run and rehearsal process",
        "P17 Go / No-Go approval record",
        "P17 post-release observation plan",
        "P16 observability readiness report",
        "P15 continuous improvement readiness report",
        "branch creation rules",
        "PR title and body rules",
        "exact-head CI requirement",
        "required check names",
        "same-branch patching",
        "manual approval requirement",
        "release calendar requirement",
        "blackout window requirement",
        "support escalation route",
        "incident escalation route",
        "restricted evidence exclusions",
        "stop conditions",
    ]:
        assert term in content


def test_p18_onboarding_checklist_documents_signoff_evidence_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "trainee name or role placeholder",
        "assigned role",
        "role owner",
        "reviewer",
        "required reading completion",
        "validation question completion",
        "evidence handling acknowledgement",
        "escalation readiness acknowledgement",
        "stop condition acknowledgement",
        "sign-off status",
        "sign-off date placeholder",
        "follow-up route",
        "Sign-off cannot be automatic.",
        "allowed evidence types are understood",
        "restricted evidence types are understood",
        "evidence sensitivity is recorded",
        "evidence source is recorded",
        "customer data export is blocked",
        "external package export is blocked",
        "raw credentials are blocked",
        "production tokens are blocked",
        "private runtime values are blocked",
        "raw logs with restricted values are blocked",
        "exact-head CI fails",
        "workflow cannot start",
        "issue scope is unclear",
        "PR scope expands",
        "owner is missing",
        "release decision is requested",
        "blackout conflict appears",
        "support case has no owner",
        "incident signal appears",
        "workflow gate bypass is requested",
    ]:
        assert term in content


def test_p18_onboarding_checklist_documents_fields_statuses_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "onboarding item identifier",
        "trainee placeholder",
        "required reading status",
        "validation question status",
        "evidence handling status",
        "escalation readiness status",
        "manual sign-off status",
        "evidence source",
        "evidence sensitivity",
        "action route",
        "action owner",
        "closure criteria",
        "not started",
        "in progress",
        "ready for review",
        "signed off",
        "signed off with notes",
        "blocked",
        "needs owner",
        "needs reviewer",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized onboarding notes",
        "summarized validation notes",
        "summarized sign-off notes",
        "summarized escalation readiness notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "rendered training materials",
        "scheduled onboarding outputs",
        "required reading is incomplete",
        "validation questions are incomplete",
        "evidence handling check is incomplete",
        "escalation readiness check is incomplete",
        "manual sign-off is missing",
        "automatic sign-off is implied",
        "production launch is implied",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "customer data export is requested",
        "external export is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic sign-off.",
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
