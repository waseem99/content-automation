from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p17-step-03.md")


def test_p17_rehearsal_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p17_rehearsal_is_simulation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This process is simulation-only.",
        "execute a production release",
        "schedule a production release",
        "approve a production release",
        "publish release notes",
        "render launch materials",
        "export release packages",
        "change production configuration",
        "run live rollback actions",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p17_rehearsal_documents_sections_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "rehearsal identifier",
        "rehearsal scope",
        "release candidate reference",
        "participant list",
        "rehearsal owner",
        "simulated release steps",
        "simulated migration steps",
        "simulated rollback steps",
        "monitoring rehearsal steps",
        "alert routing rehearsal steps",
        "communication rehearsal steps",
        "failure handling steps",
        "stop condition review",
        "evidence capture summary",
        "rehearsal decision summary",
        "rehearsal item identifier",
        "rehearsal area",
        "simulated step",
        "expected result",
        "actual result summary",
        "evidence sensitivity",
        "failure mode",
        "action route",
        "validation requirement",
        "closure criteria",
        "not started",
        "simulated successfully",
        "simulated with notes",
        "failed rehearsal",
        "blocked",
        "needs owner",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
    ]:
        assert term in content


def test_p17_rehearsal_documents_release_failure_rollback_and_communication_steps() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "release candidate verification",
        "exact-head CI evidence review",
        "release checklist review",
        "environment readiness review",
        "configuration readiness review",
        "migration readiness review",
        "rollback readiness review",
        "monitoring readiness review",
        "go/no-go handoff review",
        "post-release observation handoff",
        "failure identifier",
        "failure area",
        "observed failure summary",
        "retry decision",
        "rollback rehearsal decision",
        "Rehearsal failures must not be ignored or converted into approval without owner and evidence.",
        "rollback owner",
        "rollback trigger",
        "rollback route",
        "rollback communication route",
        "rollback validation route",
        "rollback evidence source",
        "rollback stop condition",
        "Rollback rehearsal cannot execute live rollback actions.",
        "release decision owner",
        "release communication owner",
        "incident communication owner",
        "support communication route",
        "internal update route",
        "go/no-go meeting reference",
        "Communication rehearsal cannot send or schedule public communications.",
    ]:
        assert term in content


def test_p17_rehearsal_documents_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized rehearsal notes",
        "summarized failure notes",
        "summarized rollback notes",
        "summarized monitoring notes",
        "summarized communication notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "rendered release materials",
        "scheduled release outputs",
        "rehearsal owner is missing",
        "reviewer is missing",
        "release candidate reference is missing",
        "simulated release steps are missing",
        "rollback rehearsal is missing",
        "monitoring rehearsal is missing",
        "failure handling is missing",
        "communication rehearsal is missing",
        "unresolved rehearsal failure has no action owner",
        "evidence source is missing",
        "rehearsal implies live launch",
        "rehearsal schedules a production release",
        "rehearsal sends public communication",
        "workflow gate bypass is requested",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "external export is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No public production launch without explicit decision.",
        "No live production launch during rehearsal.",
        "No release without calendar entry.",
        "No release during blackout window.",
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
