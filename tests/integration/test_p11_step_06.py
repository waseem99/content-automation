from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p11-readiness-report.md")
CHECKLIST = Path("docs/operations/p11-closeout-checklist.md")


def test_p11_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#158",
        "#159",
        "#160",
        "#161",
        "#162",
        "#163",
        "PR #164",
        "PR #165",
        "PR #166",
        "PR #167",
        "PR #168",
        "PR #169",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p11_readiness_report_records_stabilization_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-step-01.md",
        "docs/operations/p11-step-02.md",
        "docs/operations/p11-step-03.md",
        "docs/operations/p11-step-04.md",
        "docs/operations/p11-step-05.md",
        "Weekly rollout review cadence",
        "Alert tuning and threshold review",
        "Incident review cadence and action tracking",
        "Production evidence archive maintenance",
        "Operator handoff and ownership matrix",
    ]:
        assert term in content


def test_p11_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p11_step_*.py",
        "test_p11_step_01.py",
        "test_p11_step_02.py",
        "test_p11_step_03.py",
        "test_p11_step_04.py",
        "test_p11_step_05.py",
        "test_p11_step_06.py",
    ]:
        assert term in content


def test_p11_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#158 — Weekly rollout review cadence completed",
        "#159 — Alert tuning and threshold review completed",
        "#160 — Incident review cadence and action tracking completed",
        "#161 — Production evidence archive maintenance completed",
        "#162 — Operator handoff and ownership matrix completed",
        "#163 — P11 stabilization closeout prepared",
        "P11 readiness report is added",
        "P11 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p11_step_06.py`",
    ]:
        assert term in content


def test_p11_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No ownerless production action.",
        "No incident closure without evidence.",
        "No alert disablement without owner approval.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "Production lifecycle governance",
        "Release calendar governance",
        "Quarterly access review",
        "Operational KPI reporting",
        "Audit-ready production controls",
    ]:
        assert term in combined
