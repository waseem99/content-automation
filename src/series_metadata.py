"""Series and episode metadata contract helpers for P28.

These helpers define repeatable football content formats for long-form series
and related Shorts. They do not implement a CMS, scheduling, publishing,
analytics, rendering, or upload automation.
"""

from __future__ import annotations

from typing import Any

SERIES_METADATA_SCHEMA_VERSION = "p28.series_metadata.v1"
SERIES_METADATA_VALIDATION_SCHEMA_VERSION = "p28.series_metadata_validation.v1"

REQUIRED_SERIES_FIELDS = (
    "series_name",
    "series_slug",
    "episode_number",
    "recurring_question",
    "format_promise",
    "target_audience",
    "emotional_trigger",
    "next_episode_tease",
    "related_shorts",
    "packaging_connection",
    "content_package_connection",
    "publish_allowed",
    "review_required",
)

REQUIRED_RELATED_SHORT_FIELDS = (
    "short_type",
    "source_section",
    "hook",
    "p27_export_after_review",
)

REQUIRED_SERIES_NAMES = (
    "Football Pressure Index",
    "The Moment That Changed",
    "World Cup What Ifs",
    "Legacy vs Future",
)


def _series_slug(series_name: str) -> str:
    return series_name.lower().replace(" ", "-").replace("/", "-")


def _related_shorts(source_section: str, hook: str) -> list[dict[str, Any]]:
    return [
        {
            "short_type": "cold_open_cutdown",
            "source_section": "cold_open",
            "hook": hook,
            "p27_export_after_review": True,
        },
        {
            "short_type": "turning_point_cutdown",
            "source_section": source_section,
            "hook": "The moment that changed the full story.",
            "p27_export_after_review": True,
        },
        {
            "short_type": "comment_trigger_cutdown",
            "source_section": "comment_trigger",
            "hook": "The debate that should continue in comments.",
            "p27_export_after_review": True,
        },
    ]


def build_series_metadata_catalog(
    *,
    package_id: str = "pkg-p28-series-metadata",
    content_package_path: str = "content_package.json",
    produce_longform_contract_path: str = "docs/operations/p28-produce-longform-output-contract-example.json",
) -> dict[str, Any]:
    """Build a deterministic catalog of repeatable football series formats."""

    series_formats = [
        {
            "series_name": "Football Pressure Index",
            "series_slug": _series_slug("Football Pressure Index"),
            "episode_number": 1,
            "recurring_question": "Who carried the most pressure, and what did that pressure reveal?",
            "format_promise": "Rank the emotional, tactical, and legacy pressure around one player or match story.",
            "target_audience": "Football fans who enjoy pressure narratives, legacy debate, and ranked arguments.",
            "emotional_trigger": "Pressure, doubt, criticism, comeback, and reputation risk.",
            "next_episode_tease": "Next episode compares another player whose defining match changed how fans remember them.",
            "related_shorts": _related_shorts("conflict", "This player was under more pressure than most fans remember."),
        },
        {
            "series_name": "The Moment That Changed",
            "series_slug": _series_slug("The Moment That Changed"),
            "episode_number": 1,
            "recurring_question": "Which single moment changed the story, and why did it matter afterward?",
            "format_promise": "Break down one decisive football moment through context, conflict, turning point, and payoff.",
            "target_audience": "Fans who like story-led breakdowns of iconic match moments and turning points.",
            "emotional_trigger": "Shock, consequence, momentum swing, and what-if tension.",
            "next_episode_tease": "Next episode follows another moment where one decision or incident changed a football legacy.",
            "related_shorts": _related_shorts("turning_point", "One moment changed everything, but not for the reason most people think."),
        },
        {
            "series_name": "World Cup What Ifs",
            "series_slug": _series_slug("World Cup What Ifs"),
            "episode_number": 1,
            "recurring_question": "How would football memory change if one World Cup detail had gone differently?",
            "format_promise": "Explore a World Cup counterfactual while clearly separating verified history from speculation.",
            "target_audience": "World Cup fans who enjoy alternate-history debate with factual guardrails.",
            "emotional_trigger": "Regret, imagination, nostalgia, national pride, and missed opportunity.",
            "next_episode_tease": "Next episode tests another World Cup turning point that still splits fans.",
            "related_shorts": _related_shorts("question", "What if this World Cup moment went the other way?"),
        },
        {
            "series_name": "Legacy vs Future",
            "series_slug": _series_slug("Legacy vs Future"),
            "episode_number": 1,
            "recurring_question": "Is this football story about protecting a legacy or building the future?",
            "format_promise": "Compare legacy pressure against future expectations for a player, club, or national team.",
            "target_audience": "Fans who enjoy player legacy debates, next-generation comparisons, and future-facing arguments.",
            "emotional_trigger": "Expectation, succession, reputation, fear of decline, and hope.",
            "next_episode_tease": "Next episode compares another football figure caught between what they achieved and what comes next.",
            "related_shorts": _related_shorts("payoff", "Is this about legacy, or is the future already taking over?"),
        },
    ]

    for series in series_formats:
        series["packaging_connection"] = {
            "produce_longform_contract_path": produce_longform_contract_path,
            "youtube_long_form_packaging": "future_scope_after_review",
            "p27_related_shorts_exports": "allowed_after_review_only",
            "direct_publish_out_of_scope": True,
        }
        series["content_package_connection"] = {
            "content_package_path": content_package_path,
            "series_metadata_path": "docs/operations/p28-series-metadata-example.json",
            "relationship": "series metadata enriches content_package.json without replacing it",
        }
        series["publish_allowed"] = False
        series["review_required"] = True

    return {
        "schema_version": SERIES_METADATA_SCHEMA_VERSION,
        "parent_epic": 330,
        "package_id": package_id,
        "content_type": "series_metadata_catalog",
        "series_count": len(series_formats),
        "series_formats": series_formats,
        "catalog_connections": {
            "content_package_path": content_package_path,
            "produce_longform_contract_path": produce_longform_contract_path,
            "p27_platform_exports_after_review": True,
            "scheduling_automation_out_of_scope": True,
            "publishing_automation_out_of_scope": True,
        },
        "risk_fields": {
            "rights_review_required": True,
            "factual_review_required": True,
            "source_attribution_required": True,
            "editorial_review_required": True,
            "publish_allowed": False,
            "review_required": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_series_metadata_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Validate the P28 series/episode metadata contract."""

    errors: list[str] = []

    _require(catalog.get("schema_version") == SERIES_METADATA_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(catalog.get("parent_epic") == 330, errors, "parent epic must be 330")
    _require(catalog.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(catalog.get("review_required") is True, errors, "review_required must remain true")

    series_formats = catalog.get("series_formats", [])
    _require(isinstance(series_formats, list), errors, "series_formats must be a list")
    _require(len(series_formats) >= 3 if isinstance(series_formats, list) else False, errors, "at least 3 series formats required")

    seen_names: list[str] = []
    for series in series_formats if isinstance(series_formats, list) else []:
        _require(isinstance(series, dict), errors, "series entry must be an object")
        if not isinstance(series, dict):
            continue
        _require(set(REQUIRED_SERIES_FIELDS) <= set(series), errors, "series entry missing required fields")
        series_name = series.get("series_name")
        if isinstance(series_name, str):
            seen_names.append(series_name)
        for text_field in (
            "series_name",
            "series_slug",
            "recurring_question",
            "format_promise",
            "target_audience",
            "emotional_trigger",
            "next_episode_tease",
        ):
            value = series.get(text_field)
            _require(isinstance(value, str) and bool(value.strip()), errors, f"{text_field} must be non-empty text")
        _require(isinstance(series.get("episode_number"), int), errors, "episode_number must be an integer")
        related_shorts = series.get("related_shorts", [])
        _require(isinstance(related_shorts, list) and bool(related_shorts), errors, "related_shorts must be a non-empty list")
        for related_short in related_shorts if isinstance(related_shorts, list) else []:
            _require(isinstance(related_short, dict), errors, "related_short must be an object")
            if isinstance(related_short, dict):
                _require(set(REQUIRED_RELATED_SHORT_FIELDS) <= set(related_short), errors, "related_short missing required fields")
                _require(related_short.get("p27_export_after_review") is True, errors, "related short must require P27 export after review")

        packaging = series.get("packaging_connection", {})
        content_connection = series.get("content_package_connection", {})
        _require(isinstance(packaging, dict), errors, "packaging_connection must be an object")
        _require(isinstance(content_connection, dict), errors, "content_package_connection must be an object")
        if isinstance(packaging, dict):
            _require(packaging.get("direct_publish_out_of_scope") is True, errors, "direct publish must remain out of scope")
            _require("produce_longform_contract_path" in packaging, errors, "produce-longform contract connection required")
        if isinstance(content_connection, dict):
            _require(content_connection.get("content_package_path") == "content_package.json", errors, "content_package.json connection required")
        _require(series.get("publish_allowed") is False, errors, "series publish_allowed must remain false")
        _require(series.get("review_required") is True, errors, "series review_required must remain true")

    _require(set(REQUIRED_SERIES_NAMES) <= set(seen_names), errors, "required example series names missing")

    catalog_connections = catalog.get("catalog_connections", {})
    if not isinstance(catalog_connections, dict):
        catalog_connections = {}
    _require(catalog_connections.get("content_package_path") == "content_package.json", errors, "catalog content package connection required")
    _require(catalog_connections.get("p27_platform_exports_after_review") is True, errors, "P27 platform export connection required")
    _require(catalog_connections.get("scheduling_automation_out_of_scope") is True, errors, "scheduling automation must be out of scope")
    _require(catalog_connections.get("publishing_automation_out_of_scope") is True, errors, "publishing automation must be out of scope")

    risk_fields = catalog.get("risk_fields", {})
    if not isinstance(risk_fields, dict):
        risk_fields = {}
    _require(risk_fields.get("rights_review_required") is True, errors, "rights review must be required")
    _require(risk_fields.get("factual_review_required") is True, errors, "factual review must be required")
    _require(risk_fields.get("source_attribution_required") is True, errors, "source attribution must be required")
    _require(risk_fields.get("editorial_review_required") is True, errors, "editorial review must be required")
    _require(risk_fields.get("publish_allowed") is False, errors, "risk publish_allowed must remain false")
    _require(risk_fields.get("review_required") is True, errors, "risk review_required must remain true")

    return {
        "schema_version": SERIES_METADATA_VALIDATION_SCHEMA_VERSION,
        "is_valid": not errors,
        "series_count": len(series_formats) if isinstance(series_formats, list) else 0,
        "series_names_seen": seen_names,
        "required_series_names_checked": list(REQUIRED_SERIES_NAMES),
        "required_series_fields_checked": list(REQUIRED_SERIES_FIELDS),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
