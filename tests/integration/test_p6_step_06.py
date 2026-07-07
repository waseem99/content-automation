from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p6-readiness-report.md")
CHECKLIST = Path("docs/operations/p6-closeout-checklist.md")


def test_p6_report_records_scope_and_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#93",
        "#94",
        "#95",
        "#96",
        "#97",
        "#98",
        "PR #99",
        "PR #100",
        "PR #101",
        "PR #102",
        "PR #103",
        "Runtime entrypoint",
        "src.operator_api.entrypoint:app",
        "src.operator_api.entrypoint:create_runtime_app",
        "Runtime packaging notes",
        "Observability and logging contract",
        "Static operator UI shell",
        "Pilot runbook",
    ]:
        assert term in content


def test_p6_closeout_checklist_records_scope() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#93 — Runtime package and start command completed",
        "#94 — Docker and service packaging notes completed",
        "#95 — Observability and logging contract completed",
        "#96 — Minimal operator frontend skeleton completed",
        "#97 — End-to-end pilot runbook completed",
        "#98 — P6 readiness closeout prepared",
        "Final validation exists in `tests/integration/test_p6_step_06.py`",
    ]:
        assert term in content


def test_p6_closeout_docs_keep_guardrails() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No public production launch.",
    ]:
        assert term in combined
