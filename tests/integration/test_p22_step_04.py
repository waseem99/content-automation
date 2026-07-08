from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p22-step-04.md")


def test_p22_data_access_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p20-step-02.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-05.md",
    ]:
        assert term in content


def test_p22_data_access_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This data access and role review is documentation-only.",
        "grant production access",
        "remove production access",
        "change repository permissions",
        "expose restricted data",
        "approve production launch",
        "schedule access reviews",
        "publish access evidence",
        "render access evidence",
        "bypass workflow gates",
        "replace owner approval",
    ]:
        assert term in content


def test_p22_data_access_documents_boundaries_roles_rules_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "public reference data",
        "internal summary data",
        "restricted summary data",
        "suspected restricted data",
        "confirmed restricted data",
        "suspected customer data",
        "confirmed customer data",
        "blocked by guardrail data",
        "data owner",
        "evidence owner",
        "operator owner",
        "support owner",
        "incident owner",
        "release owner",
        "documentation owner",
        "backup owner",
        "no access change without named owner",
        "no sensitive access without reviewer confirmation",
        "no shared accounts",
        "no permanent elevated access",
        "no access exception without expiry or review point",
        "no access approval for customer data export",
        "no automatic access changes",
        "per role change",
        "before privacy closeout",
        "after incident signal",
        "after support escalation",
        "after drill finding",
        "monthly during steady operation",
    ]:
        assert term in content


def test_p22_data_access_documents_removal_fields_routes_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "access exceeds data class boundary",
        "exception expires",
        "evidence sensitivity changes",
        "customer data is suspected",
        "restricted value is confirmed",
        "access review identifier",
        "role name",
        "data class",
        "access boundary",
        "current access summary",
        "requested access summary",
        "approval route",
        "removal trigger status",
        "exception status",
        "approve summary-only access",
        "approve time-limited exception",
        "remove stale access",
        "escalate to data owner",
        "escalate to evidence owner",
        "escalate to incident owner",
        "access review identifier is missing",
        "access boundary is missing",
        "sensitive access lacks reviewer confirmation",
        "access approval implies customer data export",
        "secret value is present",
        "private runtime value is present",
        "No automatic approval.",
        "No automatic release.",
        "No automatic access changes.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content
