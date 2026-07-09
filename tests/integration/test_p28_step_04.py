from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.series_metadata import REQUIRED_SERIES_NAMES
from src.topic_calendar import (
    CONTENT_CALENDAR_FIELDS,
    RECOMMENDATION_STATES,
    REQUIRED_TOPIC_FIELDS,
    SCORING_DIMENSIONS,
    TOPIC_CALENDAR_SCHEMA_VERSION,
    build_topic_calendar_contract,
    validate_topic_calendar_contract,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p28-step-04.md")
EXAMPLE_PATH = Path("docs/operations/p28-topic-calendar-example.json")


def test_p28_step_04_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #359 after the PR merges.",
        "topic scoring",
        "content calendar contract",
        "recommendation states",
        "Content calendar fields",
        "src/topic_calendar.py",
        "tests/integration/test_p28_step_04.py",
    ]:
        assert term in content


def test_p28_step_04_documentation_lists_required_dimensions_calendar_fields_and_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for dimension in SCORING_DIMENSIONS:
        assert dimension in content
    for state in RECOMMENDATION_STATES:
        assert state in content
    for field in CONTENT_CALENDAR_FIELDS:
        assert field in content
    for series_name in REQUIRED_SERIES_NAMES:
        assert series_name in content

    for guardrail in [
        "scrape live trends",
        "call YouTube search-volume APIs",
        "schedule or publish content",
        "upload to platforms",
        "render media assets",
        "store platform credentials or secrets",
        "set `publish_allowed` to `true`",
        "bypass rights, factual, source attribution, or editorial review",
        "bypass P26 or P29 gates",
    ]:
        assert guardrail in content


def test_build_topic_calendar_contract_required_shape() -> None:
    contract = build_topic_calendar_contract()

    assert contract["schema_version"] == TOPIC_CALENDAR_SCHEMA_VERSION
    assert contract["parent_epic"] == 330
    assert contract["content_type"] == "topic_scoring_and_calendar_contract"
    assert tuple(contract["recommendation_states"]) == RECOMMENDATION_STATES
    assert contract["publish_allowed"] is False
    assert contract["review_required"] is True


def test_topic_calendar_scoring_rubric_and_topics() -> None:
    contract = build_topic_calendar_contract()
    dimensions = contract["scoring_rubric"]["dimensions"]

    assert set(SCORING_DIMENSIONS) <= set(dimensions)
    assert dimensions["rights_risk"]["higher_is_better"] is False
    assert dimensions["production_effort"]["higher_is_better"] is False

    for topic in contract["scored_topics"]:
        assert set(REQUIRED_TOPIC_FIELDS) <= set(topic)
        assert set(SCORING_DIMENSIONS) <= set(topic["scores"])
        for dimension in SCORING_DIMENSIONS:
            assert isinstance(topic["scores"][dimension], int)
            assert 1 <= topic["scores"][dimension] <= 5
        assert topic["recommendation_state"] in RECOMMENDATION_STATES
        assert topic["series"] in REQUIRED_SERIES_NAMES
        assert topic["publish_allowed"] is False
        assert topic["review_required"] is True


def test_topic_calendar_entries_have_required_fields() -> None:
    contract = build_topic_calendar_contract()

    for entry in contract["content_calendar"]:
        assert set(CONTENT_CALENDAR_FIELDS) <= set(entry)
        assert entry["publish_window"]
        assert entry["platform"]
        assert entry["series"] in REQUIRED_SERIES_NAMES
        assert entry["priority"]
        assert isinstance(entry["dependencies"], list)
        assert entry["review_status"]


def test_topic_calendar_contract_scope_flags_and_connections() -> None:
    contract = build_topic_calendar_contract()

    calendar_contract = contract["calendar_contract"]
    assert set(CONTENT_CALENDAR_FIELDS) <= set(calendar_contract["required_fields"])
    assert calendar_contract["publishing_automation_out_of_scope"] is True
    assert calendar_contract["live_trend_scraping_out_of_scope"] is True
    assert calendar_contract["youtube_search_volume_api_out_of_scope"] is True

    series_connection = contract["series_connection"]
    assert series_connection["series_metadata_path"] == "docs/operations/p28-series-metadata-example.json"
    assert set(REQUIRED_SERIES_NAMES) <= set(series_connection["allowed_series"])

    risk_fields = contract["risk_fields"]
    assert risk_fields["rights_review_required"] is True
    assert risk_fields["factual_review_required"] is True
    assert risk_fields["source_attribution_required"] is True
    assert risk_fields["editorial_review_required"] is True
    assert risk_fields["publish_allowed"] is False
    assert risk_fields["review_required"] is True


def test_validate_topic_calendar_contract_accepts_generated_contract() -> None:
    contract = build_topic_calendar_contract()
    result = validate_topic_calendar_contract(contract)

    assert result["schema_version"] == "p28.topic_calendar_validation.v1"
    assert result["is_valid"] is True
    assert result["scoring_dimensions_checked"] == list(SCORING_DIMENSIONS)
    assert result["recommendation_states_checked"] == list(RECOMMENDATION_STATES)
    assert result["calendar_fields_checked"] == list(CONTENT_CALENDAR_FIELDS)
    assert result["topic_count"] == 4
    assert result["calendar_entry_count"] == 4
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_validate_topic_calendar_contract_catches_missing_scoring_dimension() -> None:
    contract = build_topic_calendar_contract()
    del contract["scoring_rubric"]["dimensions"]["timeliness"]
    del contract["scored_topics"][0]["scores"]["timeliness"]

    result = validate_topic_calendar_contract(contract)

    assert result["is_valid"] is False
    assert "missing required scoring dimensions" in result["errors"]
    assert "topic missing scoring dimensions" in result["errors"]


def test_validate_topic_calendar_contract_catches_calendar_field_regression() -> None:
    contract = build_topic_calendar_contract()
    del contract["content_calendar"][0]["publish_window"]

    result = validate_topic_calendar_contract(contract)

    assert result["is_valid"] is False
    assert "calendar entry missing required fields" in result["errors"]


def test_validate_topic_calendar_contract_catches_scope_regression() -> None:
    contract = build_topic_calendar_contract()
    contract["calendar_contract"]["live_trend_scraping_out_of_scope"] = False
    contract["calendar_contract"]["youtube_search_volume_api_out_of_scope"] = False
    contract["calendar_contract"]["publishing_automation_out_of_scope"] = False

    result = validate_topic_calendar_contract(contract)

    assert result["is_valid"] is False
    assert "live trend scraping must be out of scope" in result["errors"]
    assert "YouTube search-volume API must be out of scope" in result["errors"]
    assert "publishing automation must be out of scope" in result["errors"]


def test_validate_topic_calendar_contract_catches_publish_and_review_regression() -> None:
    contract = build_topic_calendar_contract()
    contract["publish_allowed"] = True
    contract["scored_topics"][0]["publish_allowed"] = True
    contract["risk_fields"]["publish_allowed"] = True
    contract["risk_fields"]["rights_review_required"] = False

    result = validate_topic_calendar_contract(contract)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "topic publish_allowed must remain false" in result["errors"]
    assert "risk publish_allowed must remain false" in result["errors"]
    assert "rights review must be required" in result["errors"]


def test_p28_topic_calendar_example_is_valid() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_topic_calendar_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == TOPIC_CALENDAR_SCHEMA_VERSION
    assert set(SCORING_DIMENSIONS) <= set(example["scoring_rubric"]["dimensions"])
    assert tuple(example["recommendation_states"]) == RECOMMENDATION_STATES
    assert len(example["scored_topics"]) == 4
    assert len(example["content_calendar"]) == 4
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_topic_calendar_contract_output_is_deterministic() -> None:
    first = build_topic_calendar_contract()
    second = build_topic_calendar_contract()

    assert first == second
