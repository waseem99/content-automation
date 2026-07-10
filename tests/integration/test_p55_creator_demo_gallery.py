import json
from pathlib import Path

from src.p55_creator_demo_gallery import (
    P55_GALLERY_VERSION,
    build_creator_demo_gallery,
    load_demo_briefs,
)


def sample_briefs():
    return {
        "briefs": [
            {
                "demo_id": "ai-automation-founder-short",
                "topic": "AI automation for service business owners",
                "platform": "youtube_shorts",
                "audience": "small agency founders",
                "tone": "clear and practical",
                "duration_seconds": 45,
                "monetization_goal": "generate qualified leads for an AI automation consulting offer",
                "must_use_points": ["Show a before/after workflow."],
                "avoid": ["Do not promise guaranteed revenue."],
                "source_notes": ["Use owned workflow diagrams only."],
            },
            {
                "demo_id": "restaurant-launch-reel",
                "topic": "restaurant launch campaign teaser",
                "platform": "instagram_reels",
                "audience": "urban food lovers",
                "tone": "premium and warm",
                "duration_seconds": 40,
                "monetization_goal": "drive reservations and launch-week footfall",
                "must_use_points": ["Show ambience and launch CTA."],
                "avoid": ["Do not use copyrighted music."],
                "source_notes": ["Use owned footage or licensed placeholders."],
            },
        ]
    }


def test_load_demo_briefs_from_object_and_path(tmp_path):
    payload = sample_briefs()
    assert len(load_demo_briefs(payload)) == 2
    path = tmp_path / "briefs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert len(load_demo_briefs(path)) == 2


def test_build_creator_demo_gallery_writes_gallery_and_workspaces(tmp_path):
    result = build_creator_demo_gallery(sample_briefs(), tmp_path, overwrite=True)

    assert result["schema_version"] == P55_GALLERY_VERSION
    assert result["is_valid"] is True
    assert result["demo_count"] == 2
    assert result["successful_demo_count"] == 2
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["external_calls_performed"] is False

    gallery_index = Path(result["gallery_index_path"])
    gallery_json = Path(result["demo_gallery_path"])
    assert gallery_index.exists()
    assert gallery_json.exists()

    html = gallery_index.read_text(encoding="utf-8")
    assert "Creator Demo Gallery" in html
    assert "Open review workspace" in html
    assert "<script" not in html.lower()
    assert "https://" not in html.lower()
    assert "http://" not in html.lower()

    payload = json.loads(gallery_json.read_text(encoding="utf-8"))
    assert payload["demo_count"] == 2
    assert payload["ready_for_review_count"] == 2
    assert payload["human_review_required_before_production"] is True
    assert payload["hosted_ui_created"] is False

    for demo in payload["demos"]:
        workspace_index = tmp_path / demo["workspace_index_href"]
        creator_review = tmp_path / demo["creator_review_href"]
        assert workspace_index.exists()
        assert creator_review.exists()
        assert demo["local_only"] is True
        assert demo["topic"]
        assert demo["platform"]


def test_invalid_gallery_input_returns_guardrailed_error(tmp_path):
    result = build_creator_demo_gallery({"briefs": []}, tmp_path)

    assert result["is_valid"] is False
    assert "missing_demo_briefs" in result["validation_errors"]
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False
