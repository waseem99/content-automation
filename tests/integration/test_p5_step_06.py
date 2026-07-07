from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p5-readiness-report.md")
CHECKLIST = Path("docs/operations/p5-closeout-checklist.md")


def test_p5_readiness_report_records_completed_scope() -> None:
    content = REPORT.read_text(encoding="utf-8")

    required_items = [
        "#78",
        "#79",
        "#80",
        "#81",
        "#82",
        "#83",
        "PR #84",
        "PR #85",
        "PR #86",
        "PR #87",
        "PR #88",
        "Runtime entry points",
        "Runtime settings",
        "API areas",
        "Validation coverage",
        "Readiness checklist",
    ]

    for item in required_items:
        assert item in content


def test_p5_readiness_report_records_routes_and_tests() -> None:
    content = REPORT.read_text(encoding="utf-8")

    required_terms = [
        "health",
        "runtime config",
        "workflow run",
        "queue",
        "dashboard queue",
        "dashboard schema",
        "approval action",
        "audit report",
        "demo scenario",
        "test_p5_step_01.py",
        "test_p5_step_03.py",
        "test_p5_step_04.py",
        "test_p5_step_05.py",
        "test_p5_step_06.py",
    ]

    for term in required_terms:
        assert term in content


def test_p5_closeout_checklist_preserves_guardrails() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    required_terms = [
        "HTTP API skeleton completed",
        "Operator access and identity completed",
        "Runtime settings completed",
        "API contract tests completed",
        "Minimal UI contract completed",
        "Readiness closeout prepared",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No frontend framework.",
        "No bypass of review gates.",
    ]

    for term in required_terms:
        assert term in content
