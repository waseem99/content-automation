from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p39_decision_record import (
    P39_STATES,
    build_decision_record,
    build_signoff_metadata,
    render_decision_summary,
    render_follow_up_actions,
    validate_decision_state,
)

pytestmark = pytest.mark.integration


def test_p39_docs_exist() -> None:
    for issue in range(1, 7):
        path = Path(f"docs/operations/p39-step-0{issue}.md")
        assert path.exists()
        assert "P39" in path.read_text(encoding="utf-8")


def test_decision_states_validate() -> None:
    for state in P39_STATES:
        assert validate_decision_state(state)["is_valid"] is True
    assert validate_decision_state("publish_now")["is_valid"] is False


def test_record_schema_and_guardrails() -> None:
    record = build_decision_record("packet-1", "operator", "approved_local", "Looks good.")
    assert record["schema_version"] == "p39.local_decision_record.v1"
    assert record["packet_id"] == "packet-1"
    assert record["local_only"] is True
    assert record["automated_approval_performed"] is False
    assert record["publish_allowed"] is False


def test_followups_required_for_blocked_states() -> None:
    with pytest.raises(ValueError):
        build_decision_record("packet-1", "operator", "request_changes", "Needs edits.")
    record = build_decision_record("packet-1", "operator", "hold_blocked", "Blocked.", ["Resolve blocker."])
    assert record["follow_up_required"] is True
    assert "Resolve blocker." in record["follow_ups"]


def test_renderers_and_signoff() -> None:
    record = build_decision_record("packet-1", "operator", "request_changes", "Needs edits.", ["Fix copy."], signoff_name="Reviewer")
    summary = render_decision_summary(record)
    followups = render_follow_up_actions(record)
    signoff = build_signoff_metadata("operator", signoff_name="Reviewer")
    assert "Decision Summary" in summary
    assert "request_changes" in summary
    assert "Fix copy." in followups
    assert signoff["digital_signature_performed"] is False


def test_example_and_closeout() -> None:
    example = json.loads(Path("docs/operations/p39-decision-example.json").read_text(encoding="utf-8"))
    checklist = json.loads(Path("docs/operations/p39-closeout-checklist.json").read_text(encoding="utf-8"))
    report = Path("docs/operations/p39-closeout-report.md").read_text(encoding="utf-8")
    assert example["supported_states"] == list(P39_STATES)
    assert checklist["child_tasks"] == [484, 485, 486, 487, 488, 489]
    for issue in ["#484", "#485", "#486", "#487", "#488", "#489"]:
        assert issue in report
    assert "No auto-publish path." in checklist["guardrails"]
