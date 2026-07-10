import json
from pathlib import Path

from src.p57_feedback_regeneration_gallery import (
    build_feedback_regeneration_gallery,
    build_revised_brief_library,
    revise_brief,
)


def sample_briefs():
    return {
        "briefs": [
            {
                "demo_id": "restaurant-launch-reel",
                "topic": "restaurant launch campaign teaser",
                "platform": "instagram_reels",
                "audience": "urban food lovers",
                "tone": "premium, sensory",
                "duration_seconds": 40,
                "monetization_goal": "drive reservations",
                "must_use_points": ["Open with a coming-soon moment."],
                "avoid": ["Do not use copyrighted music."],
                "source_notes": ["Use original footage only."],
            },
            {
                "demo_id": "saas-founder-longform",
                "topic": "why SaaS onboarding fails",
                "platform": "youtube_long",
                "audience": "SaaS founders",
                "tone": "strategic",
                "duration_seconds": 480,
                "monetization_goal": "generate workshop leads",
                "must_use_points": ["Explain activation gap."],
                "avoid": [],
                "source_notes": [],
            },
        ]
    }


def sample_feedback():
    return {
        "schema_version": "p56.local_human_feedback_queue.v1",
        "is_valid": True,
        "approved_candidates": [
            {"demo_slug": "saas-founder-longform", "decision": "approve_for_production", "score": 84}
        ],
        "rejected_demos": [],
        "revision_queue": [
            {
                "demo_slug": "restaurant-launch-reel",
                "decision": "revise",
                "score": 72,
                "priority": "high",
                "strengths": ["Visual use case"],
                "issues": ["Needs more sensory detail"],
                "requested_changes": ["Add stronger coming-soon opening"],
            }
        ],
    }


def test_revise_brief_adds_feedback_to_brief():
    original = sample_briefs()["briefs"][0]
    item = sample_feedback()["revision_queue"][0]
    revised, patch = revise_brief(original, item)

    assert revised["demo_id"] == "restaurant-launch-reel-revised"
    assert any("Add stronger coming-soon opening" in point for point in revised["must_use_points"])
    assert any("Needs more sensory detail" in note for note in revised["avoid"])
    assert revised["revision_source"]["source_demo_slug"] == "restaurant-launch-reel"
    assert patch["priority"] == "high"


def test_build_revised_brief_library_preserves_approved_context():
    revised, summary = build_revised_brief_library(sample_briefs()["briefs"], sample_feedback())

    assert len(revised) == 1
    assert summary["revised_demo_count"] == 1
    assert summary["preserved_approved_candidates"][0]["demo_slug"] == "saas-founder-longform"
    assert summary["deployment_performed"] is False
    assert summary["upload_or_publish_performed"] is False


def test_build_feedback_regeneration_gallery_writes_local_outputs(tmp_path: Path):
    result = build_feedback_regeneration_gallery(sample_briefs(), sample_feedback(), tmp_path, overwrite=True)

    assert result["is_valid"] is True
    assert result["revised_demo_count"] == 1
    assert Path(result["revised_demo_briefs_path"]).exists()
    assert Path(result["feedback_patch_summary_path"]).exists()
    assert Path(result["feedback_regeneration_report_path"]).exists()
    assert result["revised_gallery"]["is_valid"] is True
    assert result["revised_gallery"]["demo_count"] == 1
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["external_calls_performed"] is False

    revised_payload = json.loads(Path(result["revised_demo_briefs_path"]).read_text(encoding="utf-8"))
    assert revised_payload["briefs"][0]["demo_id"].endswith("-revised")


def test_exclude_rejected_skips_rejected_items(tmp_path: Path):
    feedback = sample_feedback()
    feedback["revision_queue"][0]["decision"] = "reject"
    result = build_feedback_regeneration_gallery(sample_briefs(), feedback, tmp_path, include_rejected=False)

    assert result["is_valid"] is True
    assert result["revised_demo_count"] == 0
    patch_summary = json.loads(Path(result["feedback_patch_summary_path"]).read_text(encoding="utf-8"))
    assert patch_summary["skipped_items"][0]["reason"] == "rejected_item_excluded"


def test_invalid_feedback_is_reported(tmp_path: Path):
    result = build_feedback_regeneration_gallery(sample_briefs(), {"bad": True}, tmp_path)

    assert result["is_valid"] is False
    assert "missing_revision_queue" in result["validation_errors"]
    assert result["local_only"] is True
