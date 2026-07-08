from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p12-step-03.md")


def test_p12_kpi_reporting_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-01.md",
        "docs/operations/p12-step-02.md",
        "docs/operations/p11-step-01.md",
        "docs/operations/p11-step-02.md",
        "docs/operations/p11-step-03.md",
        "docs/operations/p11-step-04.md",
    ]:
        assert term in content


def test_p12_kpi_reporting_documents_cadence_categories_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Publish a monthly operational KPI summary.",
        "Review critical KPI breaches during weekly rollout review.",
        "release governance",
        "production health",
        "alert quality",
        "incident response",
        "access review",
        "evidence archive completeness",
        "exception aging",
        "audit control readiness",
        "KPI name",
        "actual value",
        "source evidence",
        "corrective action if needed",
    ]:
        assert term in content


def test_p12_kpi_reporting_documents_minimum_set_and_decisions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "releases completed within approved window",
        "critical alerts routed successfully",
        "incidents reviewed within cadence",
        "quarterly access review completion",
        "evidence entries with complete index fields",
        "open exceptions past review date",
        "open corrective action",
        "escalate KPI breach",
        "request release hold",
        "accept documented risk with owner and expiry date",
    ]:
        assert term in content


def test_p12_kpi_reporting_documents_evidence_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "source evidence links",
        "accepted risks",
        "archive entry",
        "KPI owner is missing",
        "critical breach has no action owner",
        "accepted risk has no expiry date",
        "No KPI report closure without source evidence.",
        "No critical breach without action owner.",
        "No accepted risk without expiry date.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
    ]:
        assert term in content
