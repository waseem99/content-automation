import json
from pathlib import Path

from src.p56_human_feedback_queue import (
    build_human_feedback_queue,
    normalize_decision,
    write_feedback_outputs,
)


def sample_gallery():
    return {
        "schema_version": "p55.local_creator_demo_gallery.v1",
        "demos": [
            {
                "demo_slug": "demo-approved-local",
                "topic": "Approved topic",
                "platform": "youtube_shorts",
                "audience": "founders",
                "workspace_index_path": "/tmp/demo-approved/index.html",
                "signals": {"rights_gate": "revise", "engagement_score": 82},
            },
            {
                "demo_slug": "demo-revise-local",
                "topic": "Revise topic",
                "platform": "instagram_reels",
                "audience": "food lovers",
                "workspace_index_path": "/tmp/demo-revise/index.html",
                "signals": {"rights_gate": "revise", "engagement_score": 70},
            },
            {
                "demo_slug": "demo-reject-local",
                "topic": "Reject topic",
                "platform": "tiktok",
                "audience": "beginners",
                "workspace_index_path": "/tmp/demo-reject/index.html",
                "signals": {"rights_gate": "block", "engagement_score": 44},
            },
            {
                "demo_slug": "demo-missing-local",
                "topic": "Missing topic",
                "platform": "youtube_long",
                "audience": "product teams",
                "workspace_index_path": "/tmp/demo-missing/index.html",
                "signals": {"rights_gate": "revise", "engagement_score": 60},
            },
        ],
    }


def sample_feedback():
    return {
        "reviewer_name": "QA Reviewer",
        "review_round": "round_1",
        "reviews": [
            {
                "demo_slug": "demo-approved-local",
                "decision": "approve_for_production",
                "score": 88,
                "strengths": ["Strong hook"],
                "issues": [],
                "requested_changes": ["Minor CTA polish"],
                "approval_notes": "Good test candidate",
            },
            {
                "demo_slug": "demo-revise-local",
                "decision": "revise",
                "score": 63,
                "strengths": ["Clear audience"],
                "issues": ["Too generic", "Storyboard weak"],
                "requested_changes": ["Make hook more specific", "Improve shot direction"],
            },
            {
                "demo_slug": "demo-reject-local",
                "decision": "reject",
                "score": 31,
                "issues": ["Rights risk", "Not useful"],
                "requested_changes": ["Rework from scratch"],
            },
        ],
    }


def test_normalize_decision_aliases_and_unknowns():
    assert normalize_decision("approve") == "approve_for_production"
    assert normalize_decision("drop") == "reject"
    assert normalize_decision("unknown") == "revise"
    assert normalize_decision(None, missing=True) == "revise"


def test_build_human_feedback_queue_counts_and_revision_priority():
    result = build_human_feedback_queue(sample_gallery(), sample_feedback())

    assert result["is_valid"] is True
    assert result["summary"]["approved_count"] == 1
    assert result["summary"]["revise_count"] == 2
    assert result["summary"]["rejected_count"] == 1
    assert result["summary"]["missing_feedback_count"] == 1
    assert len(result["approved_candidates"]) == 1
    assert len(result["revision_queue"]) == 3
    assert result["revision_queue"][0]["priority_score"] >= result["revision_queue"][-1]["priority_score"]
    assert result["local_only"] is True
    assert result["upload_or_publish_performed"] is False
    assert result["automated_final_approval"] is False


def test_write_feedback_outputs(tmp_path: Path):
    gallery_path = tmp_path / "demo_gallery.json"
    feedback_path = tmp_path / "review_feedback.json"
    gallery_path.write_text(json.dumps(sample_gallery()), encoding="utf-8")
    feedback_path.write_text(json.dumps(sample_feedback()), encoding="utf-8")

    result = write_feedback_outputs(gallery_path, feedback_path, tmp_path)

    assert result["is_valid"] is True
    assert (tmp_path / "review_feedback_summary.json").exists()
    assert (tmp_path / "revision_queue.json").exists()
    assert (tmp_path / "review_feedback_report.md").exists()
    report = (tmp_path / "review_feedback_report.md").read_text(encoding="utf-8")
    assert "Review Feedback Report" in report
    assert "Revision Queue" in report


def test_invalid_inputs_are_reported():
    result = build_human_feedback_queue({"bad": []}, sample_feedback())

    assert result["is_valid"] is False
    assert "missing_gallery_demos" in result["validation_errors"]
