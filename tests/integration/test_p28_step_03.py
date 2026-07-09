from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.series_metadata import (
    REQUIRED_RELATED_SHORT_FIELDS,
    REQUIRED_SERIES_FIELDS,
    REQUIRED_SERIES_NAMES,
    SERIES_METADATA_SCHEMA_VERSION,
    build_series_metadata_catalog,
    validate_series_metadata_catalog,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p28-step-03.md")
EXAMPLE_PATH = Path("docs/operations/p28-series-metadata-example.json")


def test_p28_step_03_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #358 after the PR merges.",
        "series and episode metadata contract",
        "series_name",
        "episode_number",
        "recurring_question",
        "format_promise",
        "target_audience",
        "emotional_trigger",
        "next_episode_tease",
        "related_shorts",
        "content_package.json",
        "src/series_metadata.py",
        "tests/integration/test_p28_step_03.py",
    ]:
        assert term in content


def test_p28_step_03_documentation_lists_required_series_and_guardrails() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for series_name in REQUIRED_SERIES_NAMES:
        assert series_name in content

    for guardrail in [
        "implement a full channel CMS",
        "schedule or publish content",
        "upload to platforms",
        "commit rendered video assets",
        "store platform credentials or secrets",
        "set `publish_allowed` to `true`",
        "bypass rights, factual, source attribution, or editorial review",
        "bypass P26 or P29 gates",
        "bypass workflow gates",
    ]:
        assert guardrail in content


def test_build_series_metadata_catalog_required_shape() -> None:
    catalog = build_series_metadata_catalog()

    assert catalog["schema_version"] == SERIES_METADATA_SCHEMA_VERSION
    assert catalog["parent_epic"] == 330
    assert catalog["content_type"] == "series_metadata_catalog"
    assert catalog["series_count"] == 4
    assert catalog["publish_allowed"] is False
    assert catalog["review_required"] is True
    assert len(catalog["series_formats"]) >= 3


def test_series_metadata_required_fields_and_examples() -> None:
    catalog = build_series_metadata_catalog()
    series_formats = catalog["series_formats"]

    assert {series["series_name"] for series in series_formats} == set(REQUIRED_SERIES_NAMES)

    for series in series_formats:
        assert set(REQUIRED_SERIES_FIELDS) <= set(series)
        assert series["series_name"]
        assert series["series_slug"]
        assert isinstance(series["episode_number"], int)
        assert series["recurring_question"]
        assert series["format_promise"]
        assert series["target_audience"]
        assert series["emotional_trigger"]
        assert series["next_episode_tease"]
        assert series["publish_allowed"] is False
        assert series["review_required"] is True


def test_series_metadata_related_shorts_and_connections() -> None:
    catalog = build_series_metadata_catalog()

    for series in catalog["series_formats"]:
        assert len(series["related_shorts"]) >= 1
        for related_short in series["related_shorts"]:
            assert set(REQUIRED_RELATED_SHORT_FIELDS) <= set(related_short)
            assert related_short["short_type"]
            assert related_short["source_section"]
            assert related_short["hook"]
            assert related_short["p27_export_after_review"] is True

        packaging = series["packaging_connection"]
        assert packaging["produce_longform_contract_path"] == "docs/operations/p28-produce-longform-output-contract-example.json"
        assert packaging["p27_related_shorts_exports"] == "allowed_after_review_only"
        assert packaging["direct_publish_out_of_scope"] is True

        content_connection = series["content_package_connection"]
        assert content_connection["content_package_path"] == "content_package.json"
        assert content_connection["series_metadata_path"] == "docs/operations/p28-series-metadata-example.json"


def test_series_metadata_catalog_connections_and_risk_fields() -> None:
    catalog = build_series_metadata_catalog()

    connections = catalog["catalog_connections"]
    assert connections["content_package_path"] == "content_package.json"
    assert connections["produce_longform_contract_path"] == "docs/operations/p28-produce-longform-output-contract-example.json"
    assert connections["p27_platform_exports_after_review"] is True
    assert connections["scheduling_automation_out_of_scope"] is True
    assert connections["publishing_automation_out_of_scope"] is True

    risk_fields = catalog["risk_fields"]
    assert risk_fields["rights_review_required"] is True
    assert risk_fields["factual_review_required"] is True
    assert risk_fields["source_attribution_required"] is True
    assert risk_fields["editorial_review_required"] is True
    assert risk_fields["publish_allowed"] is False
    assert risk_fields["review_required"] is True


def test_validate_series_metadata_catalog_accepts_generated_catalog() -> None:
    catalog = build_series_metadata_catalog()
    result = validate_series_metadata_catalog(catalog)

    assert result["schema_version"] == "p28.series_metadata_validation.v1"
    assert result["is_valid"] is True
    assert result["series_count"] == 4
    assert result["series_names_seen"] == list(REQUIRED_SERIES_NAMES)
    assert result["required_series_names_checked"] == list(REQUIRED_SERIES_NAMES)
    assert result["required_series_fields_checked"] == list(REQUIRED_SERIES_FIELDS)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_validate_series_metadata_catalog_catches_missing_required_series() -> None:
    catalog = build_series_metadata_catalog()
    catalog["series_formats"] = catalog["series_formats"][:2]

    result = validate_series_metadata_catalog(catalog)

    assert result["is_valid"] is False
    assert "at least 3 series formats required" in result["errors"]
    assert "required example series names missing" in result["errors"]


def test_validate_series_metadata_catalog_catches_missing_recurring_question_and_tease() -> None:
    catalog = build_series_metadata_catalog()
    catalog["series_formats"][0]["recurring_question"] = ""
    catalog["series_formats"][0]["next_episode_tease"] = ""

    result = validate_series_metadata_catalog(catalog)

    assert result["is_valid"] is False
    assert "recurring_question must be non-empty text" in result["errors"]
    assert "next_episode_tease must be non-empty text" in result["errors"]


def test_validate_series_metadata_catalog_catches_publish_and_scope_regression() -> None:
    catalog = build_series_metadata_catalog()
    catalog["publish_allowed"] = True
    catalog["series_formats"][0]["publish_allowed"] = True
    catalog["series_formats"][0]["packaging_connection"]["direct_publish_out_of_scope"] = False
    catalog["catalog_connections"]["publishing_automation_out_of_scope"] = False

    result = validate_series_metadata_catalog(catalog)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "series publish_allowed must remain false" in result["errors"]
    assert "direct publish must remain out of scope" in result["errors"]
    assert "publishing automation must be out of scope" in result["errors"]


def test_validate_series_metadata_catalog_catches_related_shorts_regression() -> None:
    catalog = build_series_metadata_catalog()
    catalog["series_formats"][0]["related_shorts"][0]["p27_export_after_review"] = False

    result = validate_series_metadata_catalog(catalog)

    assert result["is_valid"] is False
    assert "related short must require P27 export after review" in result["errors"]


def test_p28_series_metadata_example_is_valid() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_series_metadata_catalog(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == SERIES_METADATA_SCHEMA_VERSION
    assert example["series_count"] == 4
    assert {series["series_name"] for series in example["series_formats"]} == set(REQUIRED_SERIES_NAMES)
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_series_metadata_catalog_output_is_deterministic() -> None:
    first = build_series_metadata_catalog()
    second = build_series_metadata_catalog()

    assert first == second
