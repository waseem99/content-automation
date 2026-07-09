from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.shorts_longform_funnel import (
    CUTDOWN_MAP_FIELDS,
    FORMAT_EXAMPLES,
    FUNNEL_SCHEMA_VERSION,
    FUNNEL_TYPES,
    REQUIRED_CUTDOWN_ENTRY_FIELDS,
    TARGET_PLATFORMS,
    build_shorts_longform_funnel_contract,
    validate_shorts_longform_funnel_contract,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p28-step-05.md")
EXAMPLE_PATH = Path("docs/operations/p28-shorts-longform-funnel-example.json")


def test_p28_step_05_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #360 after the PR merges.",
        "Shorts-to-long-form funnel",
        "cutdown map",
        "source_video",
        "hook_clip",
        "cutdown_angle",
        "target_platform",
        "cta",
        "linked_long_form_episode",
        "src/shorts_longform_funnel.py",
        "tests/integration/test_p28_step_05.py",
    ]:
        assert term in content


def test_p28_step_05_documentation_lists_funnel_types_examples_and_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for funnel_type in FUNNEL_TYPES:
        assert funnel_type in content
    for field in CUTDOWN_MAP_FIELDS:
        assert field in content
    for example in FORMAT_EXAMPLES:
        assert example in content

    for guardrail in [
        "render Shorts cutdowns",
        "use analytics-based cutdown selection",
        "upload to platforms",
        "publish content",
        "scrape engagement",
        "store platform credentials or secrets",
        "commit rendered video assets",
        "set `publish_allowed` to `true`",
        "bypass rights, factual, attribution, monetization, or editorial review",
        "bypass P26 or P29 gates",
    ]:
        assert guardrail in content


def test_build_shorts_longform_funnel_contract_required_shape() -> None:
    contract = build_shorts_longform_funnel_contract()

    assert contract["schema_version"] == FUNNEL_SCHEMA_VERSION
    assert contract["parent_epic"] == 330
    assert contract["content_type"] == "shorts_longform_funnel_contract"
    assert set(FUNNEL_TYPES) <= {item["type"] for item in contract["funnel_types"]}
    assert set(CUTDOWN_MAP_FIELDS) <= set(contract["cutdown_map_fields"])
    assert contract["publish_allowed"] is False
    assert contract["review_required"] is True


def test_shorts_longform_funnel_cutdown_entries_have_required_fields() -> None:
    contract = build_shorts_longform_funnel_contract()

    assert len(contract["cutdown_map"]) >= 3
    assert set(FORMAT_EXAMPLES) <= {entry["format_example"] for entry in contract["cutdown_map"]}

    for entry in contract["cutdown_map"]:
        assert set(REQUIRED_CUTDOWN_ENTRY_FIELDS) <= set(entry)
        for field in CUTDOWN_MAP_FIELDS:
            assert isinstance(entry[field], str)
            assert entry[field]
        assert entry["funnel_type"] in FUNNEL_TYPES
        assert entry["target_platform"] in TARGET_PLATFORMS
        assert entry["review_status"] == "needs_review_before_export"
        assert entry["publish_allowed"] is False
        assert entry["review_required"] is True


def test_shorts_longform_funnel_related_episode_fields_and_connections() -> None:
    contract = build_shorts_longform_funnel_contract()

    for entry in contract["cutdown_map"]:
        related = entry["related_episode_fields"]
        assert related["episode_id"] == entry["linked_long_form_episode"]
        assert related["content_package_path"] == "content_package.json"
        assert related["longform_plan_path"]

    planning = contract["planning_connections"]
    assert planning["topic_calendar_path"] == "docs/operations/p28-topic-calendar-example.json"
    assert planning["series_metadata_path"] == "docs/operations/p28-series-metadata-example.json"
    assert planning["produce_longform_contract_path"] == "docs/operations/p28-produce-longform-output-contract-example.json"
    assert planning["content_package_path"] == "content_package.json"

    platform = contract["platform_connections"]
    assert platform["p27_export_pack_after_review"] is True
    assert platform["youtube_long_form_packaging_after_review"] is True
    assert set(TARGET_PLATFORMS) <= set(platform["target_platforms"])
    assert platform["automatic_upload_out_of_scope"] is True
    assert platform["automatic_rendering_out_of_scope"] is True
    assert platform["analytics_based_selection_out_of_scope"] is True


def test_shorts_longform_funnel_risk_fields() -> None:
    contract = build_shorts_longform_funnel_contract()
    risk_fields = contract["risk_fields"]

    assert risk_fields["rights_review_required"] is True
    assert risk_fields["factual_review_required"] is True
    assert risk_fields["source_attribution_required"] is True
    assert risk_fields["editorial_review_required"] is True
    assert risk_fields["publish_allowed"] is False
    assert risk_fields["review_required"] is True


def test_validate_shorts_longform_funnel_accepts_generated_contract() -> None:
    contract = build_shorts_longform_funnel_contract()
    result = validate_shorts_longform_funnel_contract(contract)

    assert result["schema_version"] == "p28.shorts_longform_funnel_validation.v1"
    assert result["is_valid"] is True
    assert result["funnel_types_checked"] == list(FUNNEL_TYPES)
    assert result["cutdown_map_fields_checked"] == list(CUTDOWN_MAP_FIELDS)
    assert result["format_examples_checked"] == list(FORMAT_EXAMPLES)
    assert result["cutdown_entry_count"] == 4
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_validate_shorts_longform_funnel_catches_missing_required_field() -> None:
    contract = build_shorts_longform_funnel_contract()
    del contract["cutdown_map"][0]["source_video"]

    result = validate_shorts_longform_funnel_contract(contract)

    assert result["is_valid"] is False
    assert "cutdown entry missing required fields" in result["errors"]
    assert "source_video must be non-empty text" in result["errors"]


def test_validate_shorts_longform_funnel_catches_missing_funnel_type() -> None:
    contract = build_shorts_longform_funnel_contract()
    contract["funnel_types"] = contract["funnel_types"][:2]

    result = validate_shorts_longform_funnel_contract(contract)

    assert result["is_valid"] is False
    assert "missing required funnel types" in result["errors"]


def test_validate_shorts_longform_funnel_catches_required_examples_regression() -> None:
    contract = build_shorts_longform_funnel_contract()
    contract["cutdown_map"] = [entry for entry in contract["cutdown_map"] if entry["format_example"] != "world_cup_hype"]

    result = validate_shorts_longform_funnel_contract(contract)

    assert result["is_valid"] is False
    assert "required format examples missing" in result["errors"]


def test_validate_shorts_longform_funnel_catches_scope_regression() -> None:
    contract = build_shorts_longform_funnel_contract()
    contract["platform_connections"]["automatic_rendering_out_of_scope"] = False
    contract["platform_connections"]["analytics_based_selection_out_of_scope"] = False
    contract["platform_connections"]["automatic_upload_out_of_scope"] = False

    result = validate_shorts_longform_funnel_contract(contract)

    assert result["is_valid"] is False
    assert "automatic rendering must be out of scope" in result["errors"]
    assert "analytics-based selection must be out of scope" in result["errors"]
    assert "automatic upload must be out of scope" in result["errors"]


def test_validate_shorts_longform_funnel_catches_publish_and_review_regression() -> None:
    contract = build_shorts_longform_funnel_contract()
    contract["publish_allowed"] = True
    contract["cutdown_map"][0]["publish_allowed"] = True
    contract["risk_fields"]["publish_allowed"] = True
    contract["risk_fields"]["rights_review_required"] = False

    result = validate_shorts_longform_funnel_contract(contract)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "cutdown publish_allowed must remain false" in result["errors"]
    assert "risk publish_allowed must remain false" in result["errors"]
    assert "rights review must be required" in result["errors"]


def test_p28_shorts_longform_funnel_example_is_valid() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_shorts_longform_funnel_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == FUNNEL_SCHEMA_VERSION
    assert set(FUNNEL_TYPES) <= {item["type"] for item in example["funnel_types"]}
    assert set(CUTDOWN_MAP_FIELDS) <= set(example["cutdown_map_fields"])
    assert set(FORMAT_EXAMPLES) <= {entry["format_example"] for entry in example["cutdown_map"]}
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_shorts_longform_funnel_contract_output_is_deterministic() -> None:
    first = build_shorts_longform_funnel_contract()
    second = build_shorts_longform_funnel_contract()

    assert first == second
