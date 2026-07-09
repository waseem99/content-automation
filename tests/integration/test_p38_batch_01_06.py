from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p38_navigation import (
    render_blocker_quick_links,
    render_navigation_summary,
    render_packet_toc,
    render_reviewer_quick_links,
    render_section_anchors,
    slugify_heading,
)

pytestmark = pytest.mark.integration


def test_p38_docs_exist() -> None:
    for issue in range(1, 7):
        path = Path(f"docs/operations/p38-step-0{issue}.md")
        assert path.exists()
        assert "P38" in path.read_text(encoding="utf-8")


def test_slug_and_duplicate_anchors() -> None:
    assert slugify_heading("Reviewer Checklist — Ops!") == "reviewer-checklist-ops"
    anchors = render_section_anchors(["Intro", "Intro", "Blockers"])
    assert anchors == [
        {"heading": "Intro", "anchor": "intro", "link": "#intro"},
        {"heading": "Intro", "anchor": "intro-1", "link": "#intro-1"},
        {"heading": "Blockers", "anchor": "blockers", "link": "#blockers"},
    ]


def test_toc_renderer() -> None:
    md = render_packet_toc(["Overview", "Items"])
    assert "# Table of Contents" in md
    assert "[Overview](#overview)" in md
    assert "[Items](#items)" in md


def test_reviewer_and_blocker_links() -> None:
    reviewer_md = render_reviewer_quick_links([{"checklist_id": "c1", "reviewer_role": "operator"}])
    blocker_md = render_blocker_quick_links([{"appendix_id": "b1"}])
    assert "Checklist c1" in reviewer_md
    assert "#checklist-c1-operator" in reviewer_md
    assert "Blocker Appendix b1" in blocker_md
    assert "#blocker-appendix-b1" in blocker_md


def test_navigation_summary_guardrails_and_examples() -> None:
    result = render_navigation_summary(["Overview"], [{"checklist_id": "c1", "reviewer_role": "operator"}], [{"appendix_id": "b1"}])
    assert result["schema_version"] == "p38.markdown_navigation.v1"
    assert result["markdown_only"] is True
    assert result["html_rendered"] is False
    assert result["pdf_rendered"] is False
    assert result["zip_created"] is False
    assert result["external_upload"] is False
    assert result["publish_allowed"] is False
    assert "Markdown-only local navigation" in result["markdown"]

    example = json.loads(Path("docs/operations/p38-navigation-example.json").read_text(encoding="utf-8"))
    checklist = json.loads(Path("docs/operations/p38-closeout-checklist.json").read_text(encoding="utf-8"))
    report = Path("docs/operations/p38-closeout-report.md").read_text(encoding="utf-8")
    assert example["output_format"] == "markdown_only"
    assert checklist["child_tasks"] == [476, 477, 478, 479, 480, 481]
    for issue in ["#476", "#477", "#478", "#479", "#480", "#481"]:
        assert issue in report
    assert "No auto-publish path." in checklist["guardrails"]
