from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p10-readiness-report.md")
CHECKLIST = Path("docs/operations/p10-closeout-checklist.md")


def test_p10_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#145",
        "#146",
        "#147",
        "#148",
        "#149",
        "#150",
        "PR #151",
        "PR #152",
        "PR #153",
        "PR #154",
        "PR #155",
        "This closeout PR",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p10_readiness_report_records_rollout_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-step-01.md",
        "docs/operations/p10-step-02.md",
        "docs/operations/p10-step-03.md",
        "docs/operations/p10-step-04.md",
        "docs/operations/p10-step-05.md",
        "Production exposure decision record",
        "Production deployment checklist execution",
        "Controlled exposure and smoke testing",
        "Post-rollout monitoring review",
        "First production incident drill",
    ]:
        assert term in content


def test_p10_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p10_step_*.py",
        "test_p10_step_01.py",
        "test_p10_step_02.py",
        "test_p10_step_03.py",
        "test_p10_step_04.py",
        "test_p10_step_05.py",
        "test_p10_step_06.py",
    ]:
        assert term in content


def test_p10_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#145 — Production exposure decision record completed",
        "#146 — Production deployment checklist execution completed",
        "#147 — Controlled exposure and smoke test runbook completed",
        "#148 — Post-rollout monitoring review completed",
        "#149 — First production incident drill completed",
        "#150 — P10 rollout implementation closeout prepared",
        "P10 readiness report is added",
        "P10 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p10_step_06.py`",
    ]:
        assert term in content


def test_p10_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No production exposure without explicit go decision.",
        "No exposure expansion without smoke test pass.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "Production operations stabilization",
        "Weekly rollout review",
        "Alert tuning",
        "Incident review cadence",
        "Production evidence archive maintenance",
    ]:
        assert term in combined
