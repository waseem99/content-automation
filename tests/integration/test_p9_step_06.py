from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p9-readiness-report.md")
CHECKLIST = Path("docs/operations/p9-closeout-checklist.md")


def test_p9_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#132",
        "#133",
        "#134",
        "#135",
        "#136",
        "#137",
        "PR #138",
        "PR #139",
        "PR #140",
        "PR #141",
        "PR #142",
        "PR #143",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p9_readiness_report_records_rehearsal_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p9-step-01.md",
        "docs/operations/p9-step-02.md",
        "docs/operations/p9-step-03.md",
        "docs/operations/p9-step-04.md",
        "docs/operations/p9-step-05.md",
        "Deployment dry-run",
        "Restore rehearsal",
        "Rollback rehearsal",
        "Dashboard and alert routing review",
        "Final go/no-go checklist",
    ]:
        assert term in content


def test_p9_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p9_step_*.py",
        "test_p9_step_01.py",
        "test_p9_step_02.py",
        "test_p9_step_03.py",
        "test_p9_step_04.py",
        "test_p9_step_05.py",
        "test_p9_step_06.py",
    ]:
        assert term in content


def test_p9_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#132 — Deployment dry-run runbook completed",
        "#133 — Restore rehearsal runbook completed",
        "#134 — Rollback rehearsal runbook completed",
        "#135 — Dashboard and alert routing review completed",
        "#136 — Final go/no-go checklist completed",
        "#137 — P9 rollout rehearsal closeout prepared",
        "P9 readiness report is added",
        "P9 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p9_step_06.py`",
    ]:
        assert term in content


def test_p9_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No public production launch without explicit go decision.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "Controlled production rollout implementation",
        "Production exposure decision record",
        "Post-rollout monitoring review",
        "First production incident drill",
    ]:
        assert term in combined
