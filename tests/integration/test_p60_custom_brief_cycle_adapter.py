import json
from pathlib import Path

from src.p60_custom_brief_cycle_adapter import (
    FEEDBACK_FILENAME,
    LIBRARY_FILENAME,
    MANIFEST_FILENAME,
    README_FILENAME,
    adapt_custom_brief,
    build_feedback_template,
    build_custom_library,
    demo_slug_for,
    normalize_brief_source,
)


def sample_brief():
    return {
        "demo_id": "founder-ai-audit-short",
        "topic": "AI audit for agency operations",
        "platform": "youtube_shorts",
        "audience": "agency founders with manual follow-up workflows",
        "tone": "practical, confident, founder-led",
        "duration_seconds": 45,
        "content_format": "vertical_short",
        "monetization_goal": "generate qualified leads for an AI audit",
        "must_use_points": ["Show the cost of scattered tools", "End with a checklist CTA"],
        "avoid": ["No guaranteed revenue claims"],
        "source_notes": ["Use original narration and owned diagrams only"],
    }


def test_normalize_single_brief():
    result = normalize_brief_source(sample_brief())

    assert result["is_valid"] is True
    assert result["brief"]["demo_id"] == "founder-ai-audit-short"
    assert result["brief"]["duration_seconds"] == 45
    assert result["brief"]["must_use_points"]


def test_build_library_and_feedback_template_match_slug():
    brief = normalize_brief_source(sample_brief())["brief"]
    slug = demo_slug_for(brief)
    library = build_custom_library(brief, slug)
    feedback = build_feedback_template(brief, slug)

    assert library["brief_count"] == 1
    assert library["briefs"][0]["demo_id"] == slug
    assert feedback["reviews"][0]["demo_slug"] == slug
    assert feedback["reviews"][0]["decision"] == "revise"


def test_adapt_custom_brief_writes_expected_files(tmp_path: Path):
    result = adapt_custom_brief(sample_brief(), tmp_path, overwrite=True)

    assert result["is_valid"] is True
    assert result["local_only"] is True
    assert result["upload_or_publish_performed"] is False
    assert (tmp_path / LIBRARY_FILENAME).exists()
    assert (tmp_path / FEEDBACK_FILENAME).exists()
    assert (tmp_path / MANIFEST_FILENAME).exists()
    assert (tmp_path / README_FILENAME).exists()

    library = json.loads((tmp_path / LIBRARY_FILENAME).read_text(encoding="utf-8"))
    feedback = json.loads((tmp_path / FEEDBACK_FILENAME).read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))

    assert library["briefs"][0]["demo_id"] == result["demo_slug"]
    assert feedback["reviews"][0]["demo_slug"] == result["demo_slug"]
    assert manifest["p58_command"] == result["p58_command"]
    assert "src.p58_review_cycle_runner" in result["p58_command"]


def test_adapt_custom_brief_from_file(tmp_path: Path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(sample_brief()), encoding="utf-8")
    out = tmp_path / "adapter"

    result = adapt_custom_brief(brief_path, out, overwrite=True)

    assert result["is_valid"] is True
    assert Path(result["custom_brief_library_path"]).exists()


def test_invalid_brief_reports_validation_error(tmp_path: Path):
    result = adapt_custom_brief({"platform": "youtube_shorts"}, tmp_path, overwrite=True)

    assert result["is_valid"] is False
    assert "missing_topic" in result["validation_errors"]
    assert result["local_only"] is True


def test_overwrite_protection(tmp_path: Path):
    adapt_custom_brief(sample_brief(), tmp_path, overwrite=True)

    try:
        adapt_custom_brief(sample_brief(), tmp_path, overwrite=False)
        raised = False
    except FileExistsError:
        raised = True

    assert raised is True
