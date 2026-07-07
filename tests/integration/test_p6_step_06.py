from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p6-readiness-report.md")


def test_p6_report_exists() -> None:
    assert REPORT.read_text(encoding="utf-8")
