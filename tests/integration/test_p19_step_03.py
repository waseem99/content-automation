from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p19-step-03.md")


def test_p19_data_handling_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p19_data_handling_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This data handling review is documentation-only.",
        "collect production data",
        "export customer data",
        "publish retention material",
        "render privacy material",
        "change retention settings",
        "delete production records",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
        "replace incident escalation",
    ]:
        assert term in content


def test_p19_data_handling_documents_allowed_and_prohibited_data() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized support notes",
        "summarized incident notes",
        "summarized retention notes",
        "summarized privacy review notes",
        "evidence archive entry names",
        "owner and reviewer role names",
        "non-sensitive status summaries",
        "customer data exports",
        "private runtime values",
        "secret values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "raw logs with restricted values",
        "raw support transcripts with private data",
        "raw incident dumps with private data",
        "external package exports",
        "personal data copied into closeout notes",
        "sensitive operational values copied into issues",
    ]:
        assert term in content


def test_p19_data_handling_documents_categories_retention_sensitivity_and_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "data category identifier",
        "data source",
        "allowed summary form",
        "prohibited raw form",
        "sensitivity classification",
        "retention decision",
        "deletion route",
        "escalation route",
        "evidence expectation",
        "retain summary only",
        "retain issue or PR reference only",
        "retain CI run identifier only",
        "retain evidence archive entry name only",
        "redact and retain summary",
        "reject evidence",
        "delete or replace evidence",
        "escalate to evidence owner",
        "escalate to security incident response",
        "block by guardrail",
        "Retention decisions must not authorize customer data export.",
        "public reference",
        "internal summary",
        "restricted summary",
        "restricted value suspected",
        "restricted value confirmed",
        "customer data suspected",
        "customer data confirmed",
        "retain summarized log notes only",
        "avoid raw log dumps in issues",
        "block external export of raw logs",
        "summarize the case without private data",
        "avoid customer identifiers when not required",
        "avoid raw transcript copying",
        "avoid screenshots containing restricted values",
        "Customer data exports and external package exports remain prohibited.",
    ]:
        assert term in content


def test_p19_data_handling_documents_fields_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "review item identifier",
        "data category",
        "source location",
        "sensitivity class",
        "redaction status",
        "deletion route",
        "evidence source",
        "action route",
        "validation requirement",
        "closure criteria",
        "data category is missing",
        "owner is missing",
        "reviewer is missing",
        "sensitivity class is missing",
        "retention decision is missing",
        "evidence source is missing",
        "redaction status is missing when restricted value is suspected",
        "deletion route is missing when evidence must be replaced",
        "escalation route is missing when privacy risk is suspected",
        "customer data export is requested",
        "private runtime value is present",
        "secret value is present",
        "raw credential is present",
        "production token is present",
        "external package export is requested",
        "production launch is implied",
        "workflow gate bypass is requested",
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
