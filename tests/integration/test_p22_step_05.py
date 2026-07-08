from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p22-step-05.md")


def test_p22_data_export_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p20-step-05.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-step-04.md",
        "docs/operations/p21-readiness-report.md",
    ]:
        assert term in content


def test_p22_data_export_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This data export and sharing guardrail set is documentation-only.",
        "export customer data",
        "export external packages",
        "send customer communication",
        "share restricted screenshots",
        "publish handoff materials",
        "render export materials",
        "schedule sharing activity",
        "approve production launch",
        "bypass workflow gates",
        "replace owner review",
    ]:
        assert term in content


def test_p22_data_export_documents_types_forms_and_prohibited_materials() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "customer data export",
        "external package export",
        "report sharing",
        "screenshot sharing",
        "handoff material sharing",
        "evidence archive reference sharing",
        "CI evidence reference sharing",
        "audit note sharing",
        "support note sharing",
        "incident note sharing",
        "drill note sharing",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "evidence archive entry name",
        "summarized non-sensitive note",
        "redacted summary",
        "owner-reviewed summary",
        "reviewer-approved summary",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "raw logs with restricted values",
        "screenshots containing restricted values",
        "raw support transcripts with private data",
        "package bundle exports",
        "raw dependency archives",
        "private package artifacts",
        "real phone numbers",
        "private email addresses",
        "customer identifiers",
    ]:
        assert term in content


def test_p22_data_export_documents_routes_redaction_fields_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "no export required",
        "approve summary-only sharing",
        "approve redacted summary",
        "request redaction",
        "reject with reason",
        "route to data owner",
        "route to evidence owner",
        "route to privacy owner",
        "route to security incident response",
        "route to dependency owner",
        "route to support owner",
        "remove exact restricted values",
        "replace values with named placeholders",
        "record redaction owner",
        "block closeout if redaction cannot be confirmed",
        "sharing item identifier",
        "sharing type",
        "source location",
        "data class",
        "sensitivity level",
        "intended recipient category placeholder",
        "allowed sharing form",
        "prohibited material status",
        "approval route",
        "redaction status",
        "sharing item identifier is missing",
        "intended recipient category placeholder is missing",
        "customer data export is requested",
        "external package export is requested",
        "package bundle export is requested",
        "screenshot contains restricted value",
        "real contact detail is present",
        "customer identifier is present",
        "external communication is implied",
        "No automatic approval.",
        "No automatic release.",
        "No automatic export.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No customer data exports.",
        "No external package exports.",
        "No external export.",
    ]:
        assert term in content
