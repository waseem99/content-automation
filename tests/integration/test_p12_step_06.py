from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p12-readiness-report.md")
CHECKLIST = Path("docs/operations/p12-closeout-checklist.md")


def test_p12_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#171",
        "#172",
        "#173",
        "#174",
        "#175",
        "#176",
        "PR #177",
        "PR #178",
        "PR #179",
        "PR #180",
        "PR #181",
        "PR #182",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p12_readiness_report_records_governance_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-01.md",
        "docs/operations/p12-step-02.md",
        "docs/operations/p12-step-03.md",
        "docs/operations/p12-step-04.md",
        "docs/operations/p12-step-05.md",
        "Release calendar governance",
        "Quarterly access review",
        "Operational KPI reporting",
        "Audit-ready production controls",
        "Governance exception handling",
    ]:
        assert term in content


def test_p12_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p12_step_*.py",
        "test_p12_step_01.py",
        "test_p12_step_02.py",
        "test_p12_step_03.py",
        "test_p12_step_04.py",
        "test_p12_step_05.py",
        "test_p12_step_06.py",
    ]:
        assert term in content


def test_p12_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#171 — Release calendar governance completed",
        "#172 — Quarterly access review completed",
        "#173 — Operational KPI reporting completed",
        "#174 — Audit-ready production controls completed",
        "#175 — Governance exception handling completed",
        "#176 — P12 lifecycle governance closeout prepared",
        "P12 readiness report is added",
        "P12 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p12_step_06.py`",
    ]:
        assert term in content


def test_p12_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No access review closure with missing inventory.",
        "No critical breach without action owner.",
        "No control closure without evidence.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "Production maturity and resilience",
        "Disaster recovery review",
        "Backup and restore evidence",
        "Failover readiness",
        "Capacity planning",
        "Resilience drill cadence",
    ]:
        assert term in combined
