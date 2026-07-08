from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p13-readiness-report.md")
CHECKLIST = Path("docs/operations/p13-closeout-checklist.md")


def test_p13_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#184",
        "#185",
        "#186",
        "#187",
        "#188",
        "#189",
        "PR #190",
        "PR #191",
        "PR #192",
        "PR #193",
        "PR #194",
        "PR #195",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p13_readiness_report_records_resilience_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p13-step-01.md",
        "docs/operations/p13-step-02.md",
        "docs/operations/p13-step-03.md",
        "docs/operations/p13-step-04.md",
        "docs/operations/p13-step-05.md",
        "Disaster recovery review",
        "Backup and restore evidence",
        "Failover readiness",
        "Capacity planning",
        "Resilience drill cadence",
    ]:
        assert term in content


def test_p13_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p13_step_*.py",
        "test_p13_step_01.py",
        "test_p13_step_02.py",
        "test_p13_step_03.py",
        "test_p13_step_04.py",
        "test_p13_step_05.py",
        "test_p13_step_06.py",
    ]:
        assert term in content


def test_p13_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#184 — Disaster recovery review completed",
        "#185 — Backup and restore evidence completed",
        "#186 — Failover readiness completed",
        "#187 — Capacity planning completed",
        "#188 — Resilience drill cadence completed",
        "#189 — P13 maturity and resilience closeout prepared",
        "P13 readiness report is added",
        "P13 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p13_step_06.py`",
    ]:
        assert term in content


def test_p13_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No disaster recovery review closure without evidence.",
        "No backup review closure without evidence.",
        "No failover readiness closure without validation evidence.",
        "No capacity review closure without evidence.",
        "No drill closure without evidence.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "Production compliance and audit readiness",
        "Compliance evidence mapping",
        "Security review cadence",
        "Access certification",
        "Control testing",
        "Audit package preparation",
    ]:
        assert term in combined
