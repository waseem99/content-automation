"""produce-longform command and output contract helpers for P28.

This module describes the future CLI/output contract for long-form 16:9
YouTube planning. It does not implement full assembly, rendering, upload,
analytics ingestion, rights clearance, or editorial approval.
"""

from __future__ import annotations

from typing import Any

from src.long_form_concept import build_long_form_concept, validate_long_form_concept

PRODUCE_LONGFORM_SCHEMA_VERSION = "p28.produce_longform_contract.v1"
PRODUCE_LONGFORM_COMMAND = "produce-longform"
PRODUCE_LONGFORM_OUTPUT_DIRECTORY_TEMPLATE = "outputs/longform/{package_id}/"

REQUIRED_PRODUCE_LONGFORM_OUTPUTS = (
    "longform_plan.json",
    "chapter_script.md",
    "source_list.json",
    "thumbnail_concepts.json",
    "chapter_timestamps.json",
    "sponsor_slot_notes.md",
    "final_video_placeholder.txt",
    "content_package_link.json",
    "platform_export_links.json",
    "risk_review.json",
    "metadata.json",
)

REQUIRED_CLI_ARGUMENTS = (
    "--concept",
    "--topic",
    "--subject",
    "--output-dir",
    "--content-package",
    "--risk-report",
    "--source-attribution",
    "--duration-minutes",
    "--review-only",
    "--dry-run",
)

REQUIRED_RISK_FIELDS = (
    "rights_review_required",
    "factual_review_required",
    "monetization_review_required",
    "source_attribution_required",
    "editorial_review_required",
    "publish_allowed",
    "review_required",
)


def _clean_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def build_produce_longform_contract(
    topic: str,
    *,
    subject: str | None = None,
    package_id: str = "pkg-p28-longform-neymar-2014",
    output_dir: str | None = None,
    concept_path: str = "docs/operations/p28-long-form-concept-example.json",
    content_package_path: str = "content_package.json",
    risk_report_path: str = "monetization_risk_report.json",
    source_attribution_path: str = "source_attribution.json",
) -> dict[str, Any]:
    """Build a deterministic future command/output contract."""

    topic_text = _clean_text(topic, field_name="topic")
    package_id_text = _clean_text(package_id, field_name="package_id")
    output_directory = output_dir or PRODUCE_LONGFORM_OUTPUT_DIRECTORY_TEMPLATE.format(package_id=package_id_text)
    concept = build_long_form_concept(topic_text, subject=subject)

    return {
        "schema_version": PRODUCE_LONGFORM_SCHEMA_VERSION,
        "command": PRODUCE_LONGFORM_COMMAND,
        "objective": "Design-only output contract for future 16:9 YouTube long-form generation.",
        "status": "design_only_not_implemented",
        "package_id": package_id_text,
        "output_directory": output_directory,
        "cli_arguments": [
            {
                "name": "--concept",
                "required": True,
                "example": concept_path,
                "purpose": "Path to the validated P28 long-form concept JSON/YAML input.",
            },
            {
                "name": "--topic",
                "required": True,
                "example": topic_text,
                "purpose": "Football story/topic for the long-form plan.",
            },
            {
                "name": "--subject",
                "required": False,
                "example": concept["subject"],
                "purpose": "Main player, club, match, tournament, or story subject.",
            },
            {
                "name": "--output-dir",
                "required": True,
                "example": output_directory,
                "purpose": "Target folder for planned long-form outputs.",
            },
            {
                "name": "--content-package",
                "required": True,
                "example": content_package_path,
                "purpose": "Existing content_package.json or future generated package bridge.",
            },
            {
                "name": "--risk-report",
                "required": True,
                "example": risk_report_path,
                "purpose": "P26 risk report input that must remain visible in outputs.",
            },
            {
                "name": "--source-attribution",
                "required": True,
                "example": source_attribution_path,
                "purpose": "Source attribution input used to create source_list.json.",
            },
            {
                "name": "--duration-minutes",
                "required": False,
                "example": str(concept["target_duration_minutes"]),
                "purpose": "Target duration constrained by the long-form concept model.",
            },
            {
                "name": "--review-only",
                "required": True,
                "example": "true",
                "purpose": "Forces review-only outputs and publish_allowed false.",
            },
            {
                "name": "--dry-run",
                "required": False,
                "example": "true",
                "purpose": "Validates inputs and output plan without producing media assets.",
            },
        ],
        "expected_inputs": {
            "concept": concept_path,
            "content_package": content_package_path,
            "risk_report": risk_report_path,
            "source_attribution": source_attribution_path,
            "rights_review_state": "required_before_assembly",
            "editorial_review_state": "required_before_publish_ready",
        },
        "planned_outputs": {
            "longform_plan.json": {
                "path": output_directory + "longform_plan.json",
                "purpose": "Full production plan with concept, chapter map, packaging bridge, and review state.",
                "contains": ["concept", "chapters", "target_duration", "output_manifest", "risk_fields"],
            },
            "chapter_script.md": {
                "path": output_directory + "chapter_script.md",
                "purpose": "Draft long-form chapter script organized by section type.",
                "contains": ["cold_open", "question", "context", "conflict", "turning_point", "payoff", "comment_trigger"],
            },
            "source_list.json": {
                "path": output_directory + "source_list.json",
                "purpose": "Source list and attribution plan for facts, visuals, and recreated assets.",
                "contains": ["source_attribution", "minimum_sources", "rights_status", "factual_status"],
            },
            "thumbnail_concepts.json": {
                "path": output_directory + "thumbnail_concepts.json",
                "purpose": "Thumbnail concepts for future human design review.",
                "contains": ["hook", "composition", "text_overlay", "risk_notes"],
            },
            "chapter_timestamps.json": {
                "path": output_directory + "chapter_timestamps.json",
                "purpose": "Approximate chapter timestamps for YouTube description packaging.",
                "contains": ["start_time", "section_type", "title", "duration_seconds"],
            },
            "sponsor_slot_notes.md": {
                "path": output_directory + "sponsor_slot_notes.md",
                "purpose": "Placeholder-only sponsor slot notes from the long-form concept.",
                "contains": ["slot", "target_time", "max_duration", "placeholder_only"],
            },
            "final_video_placeholder.txt": {
                "path": output_directory + "final_video_placeholder.txt",
                "purpose": "Target final video location/name placeholder; no rendered video is produced in P28-02.",
                "contains": ["target_filename", "rendering_out_of_scope", "manual_review_required"],
            },
            "content_package_link.json": {
                "path": output_directory + "content_package_link.json",
                "purpose": "Bridge from long-form plan back to content_package.json.",
                "contains": ["content_package_path", "longform_plan_path", "source_package_status"],
            },
            "platform_export_links.json": {
                "path": output_directory + "platform_export_links.json",
                "purpose": "Bridge from long-form sections to future P27/P28 platform export packs after review.",
                "contains": ["youtube_long_form", "shorts_funnel", "p27_exports_after_review"],
            },
            "risk_review.json": {
                "path": output_directory + "risk_review.json",
                "purpose": "Risk fields carried into the long-form output manifest.",
                "contains": list(REQUIRED_RISK_FIELDS),
            },
            "metadata.json": {
                "path": output_directory + "metadata.json",
                "purpose": "Command metadata, schema, package id, output folder, and review-only flags.",
                "contains": ["schema_version", "command", "package_id", "publish_allowed", "review_required"],
            },
        },
        "content_package_connection": {
            "input_path": content_package_path,
            "planned_output_path": output_directory + "content_package_link.json",
            "relationship": "long-form outputs must reference the source content package instead of replacing it.",
            "required_fields": ["content_package_path", "longform_plan_path", "risk_report_path", "source_attribution_path"],
        },
        "platform_export_connection": {
            "planned_output_path": output_directory + "platform_export_links.json",
            "youtube_long_form_packaging": "future_scope_after_review",
            "shorts_cutdowns": "may use P27 platform export packs only after P26/P29 review gates",
            "direct_upload": "out_of_scope",
        },
        "risk_fields": {
            "rights_review_required": True,
            "factual_review_required": True,
            "monetization_review_required": True,
            "source_attribution_required": True,
            "editorial_review_required": True,
            "publish_allowed": False,
            "review_required": True,
        },
        "example_command": (
            f"{PRODUCE_LONGFORM_COMMAND} --concept {concept_path} --topic \"{topic_text}\" "
            f"--subject \"{concept['subject']}\" --output-dir {output_directory} "
            f"--content-package {content_package_path} --risk-report {risk_report_path} "
            f"--source-attribution {source_attribution_path} --duration-minutes {concept['target_duration_minutes']} "
            "--review-only true --dry-run true"
        ),
        "concept_validation": validate_long_form_concept(concept),
        "out_of_scope": [
            "full long-form assembly",
            "16:9 video rendering",
            "YouTube upload",
            "YouTube Studio analytics ingestion",
            "automatic rights clearance",
            "automatic editorial approval",
        ],
        "guardrails": [
            "No 16:9 rendering in P28-02.",
            "No direct YouTube upload.",
            "No platform credentials.",
            "No external video asset commits.",
            "No secret values.",
            "No automatic publish approval.",
            "No bypass of P26 or P29 gates.",
        ],
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_produce_longform_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the produce-longform design contract."""

    errors: list[str] = []

    _require(contract.get("schema_version") == PRODUCE_LONGFORM_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(contract.get("command") == PRODUCE_LONGFORM_COMMAND, errors, "command must be produce-longform")
    _require(contract.get("status") == "design_only_not_implemented", errors, "status must remain design_only_not_implemented")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    cli_argument_names = [argument.get("name") for argument in contract.get("cli_arguments", []) if isinstance(argument, dict)]
    _require(set(REQUIRED_CLI_ARGUMENTS) <= set(cli_argument_names), errors, "missing required CLI arguments")

    planned_outputs = contract.get("planned_outputs", {})
    if not isinstance(planned_outputs, dict):
        planned_outputs = {}
    _require(set(REQUIRED_PRODUCE_LONGFORM_OUTPUTS) <= set(planned_outputs), errors, "missing required planned outputs")

    for output_name in REQUIRED_PRODUCE_LONGFORM_OUTPUTS:
        output = planned_outputs.get(output_name, {})
        _require(isinstance(output, dict), errors, f"{output_name} output must be an object")
        if isinstance(output, dict):
            _require(output.get("path", "").endswith(output_name), errors, f"{output_name} path mismatch")
            _require(bool(output.get("purpose")), errors, f"{output_name} purpose required")
            _require(bool(output.get("contains")), errors, f"{output_name} contains list required")

    risk_fields = contract.get("risk_fields", {})
    if not isinstance(risk_fields, dict):
        risk_fields = {}
    _require(set(REQUIRED_RISK_FIELDS) <= set(risk_fields), errors, "missing required risk fields")
    _require(risk_fields.get("publish_allowed") is False, errors, "risk publish_allowed must remain false")
    _require(risk_fields.get("review_required") is True, errors, "risk review_required must remain true")
    _require(risk_fields.get("rights_review_required") is True, errors, "rights review must be required")
    _require(risk_fields.get("factual_review_required") is True, errors, "factual review must be required")
    _require(risk_fields.get("editorial_review_required") is True, errors, "editorial review must be required")

    content_connection = contract.get("content_package_connection", {})
    platform_connection = contract.get("platform_export_connection", {})
    _require(isinstance(content_connection, dict), errors, "content_package_connection must be an object")
    _require(isinstance(platform_connection, dict), errors, "platform_export_connection must be an object")
    if isinstance(content_connection, dict):
        _require(content_connection.get("input_path") == "content_package.json", errors, "content_package.json connection required")
    if isinstance(platform_connection, dict):
        _require(platform_connection.get("direct_upload") == "out_of_scope", errors, "direct upload must remain out of scope")
        _require("P27" in platform_connection.get("shorts_cutdowns", ""), errors, "P27 export connection required")

    example_command = contract.get("example_command", "")
    _require(isinstance(example_command, str) and PRODUCE_LONGFORM_COMMAND in example_command, errors, "example command required")
    for argument in REQUIRED_CLI_ARGUMENTS:
        _require(argument in example_command, errors, f"example command missing {argument}")

    out_of_scope = contract.get("out_of_scope", [])
    guardrails = contract.get("guardrails", [])
    _require("16:9 video rendering" in out_of_scope, errors, "rendering out-of-scope note required")
    _require("YouTube upload" in out_of_scope, errors, "YouTube upload out-of-scope note required")
    _require("No direct YouTube upload." in guardrails, errors, "direct upload guardrail required")
    _require("No 16:9 rendering in P28-02." in guardrails, errors, "rendering guardrail required")

    concept_validation = contract.get("concept_validation", {})
    _require(isinstance(concept_validation, dict), errors, "concept_validation must be an object")
    if isinstance(concept_validation, dict):
        _require(concept_validation.get("is_valid") is True, errors, "concept validation must be valid")

    return {
        "schema_version": "p28.produce_longform_contract_validation.v1",
        "is_valid": not errors,
        "command": contract.get("command"),
        "required_cli_arguments_checked": list(REQUIRED_CLI_ARGUMENTS),
        "required_outputs_checked": list(REQUIRED_PRODUCE_LONGFORM_OUTPUTS),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
