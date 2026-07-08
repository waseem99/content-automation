from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p22-step-03.md")


def test_p22_privacy_safe_evidence_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-02.md",
        "docs/operations/p21-readiness-report.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p20-step-04.md",
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p22_privacy_safe_evidence_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This privacy-safe evidence checklist is documentation-only.",
        "collect production data",
        "export customer data",
        "expose secret values",
        "expose private runtime values",
        "publish evidence",
        "render evidence",
        "schedule evidence reviews",
        "approve production launch",
        "bypass workflow gates",
        "replace owner review",
    ]:
        assert term in content


def test_p22_privacy_safe_evidence_documents_surfaces_summaries_and_prohibited_values() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "CI evidence",
        "workflow logs",
        "audit notes",
        "support notes",
        "incident notes",
        "drill records",
        "closeout reports",
        "readiness reports",
        "PR comments",
        "issue comments",
        "screenshots",
        "handoff materials",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "summarized log note",
        "summarized support note",
        "summarized incident note",
        "summarized audit note",
        "summarized drill note",
        "summarized reviewer note",
        "evidence archive entry name",
        "customer data",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "raw support transcripts with private data",
        "screenshots containing restricted values",
        "private email addresses",
        "real phone numbers",
        "external package exports",
    ]:
        assert term in content


def test_p22_privacy_safe_evidence_documents_review_fields_escalation_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "evidence surface is identified",
        "allowed summary form is used",
        "prohibited value scan is complete",
        "evidence owner is recorded",
        "reviewer is recorded",
        "evidence sensitivity is recorded",
        "retention decision is recorded",
        "deletion or replacement route is recorded when required",
        "checklist item identifier",
        "evidence surface",
        "allowed summary form",
        "prohibited value status",
        "evidence owner",
        "retention decision",
        "validation requirement",
        "prohibited value is suspected",
        "prohibited value is confirmed",
        "customer data is suspected",
        "screenshot contains restricted value",
        "raw transcript contains private data",
        "checklist item identifier is missing",
        "allowed summary form is missing",
        "prohibited value status is missing",
        "prohibited value remains in evidence",
        "customer data export is requested",
        "secret value is present",
        "private runtime value is present",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
