from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p37_markdown import (
    render_blocker_appendix,
    render_full_markdown_packet,
    render_item_table,
    render_local_handoff,
    render_packet_overview,
    render_reviewer_checklist,
)

pytestmark = pytest.mark.integration


def _packet() -> dict:
    return {
        "packet_id": "packet-1",
        "packet_title": "Local Review Packet",
        "generated_at": "manual",
        "warnings": ["review_required"],
        "counts": {"total_items": 1, "required_items": 1},
        "items": [
            {
                "section": "review_required",
                "title": "Report",
                "item_type": "report",
                "relative_path": "report.md",
                "review_status": "review_required",
                "reviewer_role": "operator",
                "required": True,
                "checksum_digest": "abc123",
            }
        ],
    }


def _checklist() -> dict:
    return {
        "checklist_id": "checklist-1",
        "reviewer_role": "operator",
        "gates": ["completeness", "governance"],
        "required_items": ["report"],
        "decision_options": ["approve_local_packet", "request_changes"],
    }


def _appendix() -> dict:
    return {
        "appendix_id": "appendix-1",
        "blockers": [
            {
                "blocker_type": "governance_block",
                "severity": "high",
                "source_item_id": "report",
                "owner_role": "operator",
                "required_resolution": "Review manually.",
                "reviewer_notes": "No automation.",
            }
        ],
    }


def _manifest() -> dict:
    return {
        "manifest_id": "manifest-1",
        "packet_id": "packet-1",
        "distribution_status": "local_only_not_sent",
        "packet_files": ["report.md"],
        "reviewer_roles": ["operator"],
        "checklist_ids": ["checklist-1"],
        "blocker_appendices": ["appendix-1"],
        "next_local_steps": ["Review locally."],
    }


def test_p37_docs_exist() -> None:
    for issue in range(1, 7):
        path = Path(f"docs/operations/p37-step-0{issue}.md")
        assert path.exists()
        assert "P37" in path.read_text(encoding="utf-8")


def test_overview_renderer() -> None:
    md = render_packet_overview(_packet())
    assert "# Local Review Packet" in md
    assert "Packet ID: `packet-1`" in md
    assert "Total items: 1" in md
    assert "review_required" in md
    assert "Markdown-only local output" in md


def test_item_table_renderer() -> None:
    md = render_item_table(_packet())
    assert "| Section | Title | Type | Path | Status | Reviewer | Required | Checksum |" in md
    assert "| review_required | Report | report | `report.md` | review_required | operator | yes | `abc123` |" in md


def test_checklist_renderer() -> None:
    md = render_reviewer_checklist(_checklist())
    assert "Reviewer Checklist" in md
    assert "completeness" in md
    assert "approve_local_packet" in md
    assert "human_only_local_review" in md


def test_blocker_renderer() -> None:
    md = render_blocker_appendix(_appendix())
    assert "governance_block" in md
    assert "Review manually." in md
    assert "No automated remediation" in md


def test_handoff_renderer() -> None:
    md = render_local_handoff(_manifest())
    assert "Distribution: `local_only_not_sent`" in md
    assert "report.md" in md
    assert "Review locally." in md


def test_full_packet_guardrails_and_example() -> None:
    result = render_full_markdown_packet(_packet(), [_checklist()], [_appendix()], _manifest())
    assert result["schema_version"] == "p37.markdown_renderer.v1"
    assert result["markdown_only"] is True
    assert result["html_rendered"] is False
    assert result["pdf_rendered"] is False
    assert result["zip_created"] is False
    assert result["external_upload"] is False
    assert result["publish_allowed"] is False
    assert result["section_count"] == 5
    assert "---" in result["markdown"]

    example = json.loads(Path("docs/operations/p37-markdown-example.json").read_text(encoding="utf-8"))
    checklist = json.loads(Path("docs/operations/p37-closeout-checklist.json").read_text(encoding="utf-8"))
    report = Path("docs/operations/p37-closeout-report.md").read_text(encoding="utf-8")
    assert example["output_format"] == "markdown_only"
    assert checklist["child_tasks"] == [468, 469, 470, 471, 472, 473]
    for issue in ["#468", "#469", "#470", "#471", "#472", "#473"]:
        assert issue in report
    assert "No auto-publish path." in checklist["guardrails"]
