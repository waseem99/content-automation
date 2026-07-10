import json
from pathlib import Path

from src.p58_review_cycle_runner import run_local_review_cycle


def sample_briefs():
    return {
        "briefs": [
            {
                "demo_id": "agency-ai-short",
                "topic": "AI automation checklist for agency owners",
                "platform": "youtube_shorts",
                "audience": "small agency owners",
                "tone": "practical, direct, trustworthy",
                "duration_seconds": 45,
                "monetization_goal": "generate qualified leads for an automation audit",
                "must_use_points": ["Open with wasted manual admin time", "Show a simple before and after workflow"],
                "avoid": ["Do not promise guaranteed revenue"],
                "source_notes": ["Use owned diagrams and original narration only"],
            },
            {
                "demo_id": "restaurant-launch-short",
                "topic": "restaurant launch teaser",
                "platform": "instagram_reels",
                "audience": "urban food lovers",
                "tone": "premium, warm, sensory",
                "duration_seconds": 40,
                "monetization_goal": "drive launch week reservations",
                "must_use_points": ["Open with a coming soon moment", "Show ambience and food energy"],
                "avoid": ["Do not use copyrighted music"],
                "source_notes": ["Use original restaurant footage only"],
            },
        ]
    }


def sample_feedback():
    return {
        "reviewer_name": "QA Reviewer",
        "review_round": "p58_test_round",
        "reviews": [
            {
                "demo_slug": "agency-ai-short",
                "decision": "approve_for_production",
                "score": 86,
                "strengths": ["Clear business pain"],
                "issues": [],
                "requested_changes": ["Make the opening more founder-specific"],
                "approval_notes": "Good enough for a production test",
            },
            {
                "demo_slug": "restaurant-launch-short",
                "decision": "revise",
                "score": 66,
                "strengths": ["Visual use case"],
                "issues": ["Needs stronger sensory direction"],
                "requested_changes": ["Make the storyboard more ambience-led"],
                "approval_notes": "Needs another pass",
            },
        ],
    }


def test_run_local_review_cycle_creates_master_outputs(tmp_path: Path):
    result = run_local_review_cycle(sample_briefs(), sample_feedback(), tmp_path, overwrite=True)

    assert result["is_valid"] is True
    assert result["schema_version"] == "p58.one_command_local_review_cycle.v1"
    assert result["demo_count"] == 2
    assert result["revision_queue_count"] == 1
    assert result["revised_demo_count"] == 1
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False

    index_path = Path(result["review_cycle_index_path"])
    summary_path = Path(result["review_cycle_summary_path"])
    report_path = Path(result["operator_run_report_path"])

    assert index_path.exists()
    assert summary_path.exists()
    assert report_path.exists()
    assert "Original Gallery" in index_path.read_text(encoding="utf-8")
    assert "Revised Gallery" in index_path.read_text(encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["counts"]["original_demo_count"] == 2
    assert summary["counts"]["approved_count"] == 1
    assert summary["counts"]["revision_queue_count"] == 1
    assert summary["counts"]["revised_demo_count"] == 1
    assert summary["human_review_required_before_production"] is True

    assert (tmp_path / "original-gallery" / "index.html").exists()
    assert (tmp_path / "feedback" / "review_feedback_report.md").exists()
    assert (tmp_path / "regeneration" / "revised-gallery" / "index.html").exists()


def test_run_local_review_cycle_handles_invalid_briefs(tmp_path: Path):
    result = run_local_review_cycle({"briefs": []}, sample_feedback(), tmp_path, overwrite=True)

    assert result["is_valid"] is False
    assert result["failed_step"] == "original_gallery"
    assert result["deployment_performed"] is False
    assert result["external_calls_performed"] is False


def test_run_local_review_cycle_can_exclude_rejected_items(tmp_path: Path):
    feedback = sample_feedback()
    feedback["reviews"][1]["decision"] = "reject"

    result = run_local_review_cycle(
        sample_briefs(),
        feedback,
        tmp_path,
        include_rejected=False,
        overwrite=True,
    )

    assert result["is_valid"] is True
    assert result["revision_queue_count"] == 1
    assert result["revised_demo_count"] == 0
    summary = json.loads(Path(result["review_cycle_summary_path"]).read_text(encoding="utf-8"))
    assert summary["counts"]["skipped_count"] == 1
