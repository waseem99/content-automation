from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p22-step-02.md")


def test_p22_retention_policy_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p22-step-01.md",
        "docs/operations/p20-step-04.md",
        "docs/operations/p20-readiness-report.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p18-step-05.md",
    ]:
        assert term in content


def test_p22_retention_policy_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This retention and deletion policy is documentation-only.",
        "delete production records",
        "change retention settings",
        "collect production data",
        "export customer data",
        "store restricted values",
        "approve production launch",
        "schedule deletion jobs",
        "publish retention evidence",
        "render retention evidence",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p22_retention_policy_documents_windows_triggers_archive_and_routes() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "retain issue or PR reference only",
        "retain CI run identifier only",
        "retain merge commit reference only",
        "retain evidence archive entry name only",
        "retain summary until phase closeout",
        "retain summary until owner review",
        "reject evidence immediately",
        "delete or replace evidence immediately",
        "customer data is suspected",
        "customer data is confirmed",
        "secret value is suspected",
        "private runtime value is suspected",
        "restricted value appears in notes",
        "raw log contains restricted value",
        "screenshot contains restricted value",
        "evidence is not summary-only",
        "summarized deletion note",
        "summarized replacement note",
        "replace with issue or PR reference",
        "replace with summarized non-sensitive note",
        "route to privacy owner",
        "route to security incident response",
        "create documentation issue",
        "create implementation issue",
    ]:
        assert term in content


def test_p22_retention_policy_documents_fields_statuses_owner_review_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "deletion evidence identifier",
        "source location",
        "data class",
        "sensitivity level",
        "deletion trigger",
        "retention window",
        "replacement route",
        "deletion status",
        "validation requirement",
        "not required",
        "replacement required",
        "replaced with summary",
        "rejected with reason",
        "owner review required",
        "incident escalation required",
        "blocked by guardrail",
        "data class is recorded",
        "sensitivity level is recorded",
        "retention window is valid",
        "evidence is summary-only",
        "restricted values are not retained",
        "deletion evidence identifier is missing",
        "retention window is missing",
        "replacement route is missing when replacement is required",
        "customer data export is requested",
        "secret value is present",
        "private runtime value is present",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic deletion.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
