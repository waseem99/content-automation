from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.long_form_command_contract import (
    PRODUCE_LONGFORM_COMMAND,
    PRODUCE_LONGFORM_OUTPUT_DIRECTORY_TEMPLATE,
    PRODUCE_LONGFORM_SCHEMA_VERSION,
    REQUIRED_CLI_ARGUMENTS,
    REQUIRED_PRODUCE_LONGFORM_OUTPUTS,
    REQUIRED_RISK_FIELDS,
    build_produce_longform_contract,
    validate_produce_longform_contract,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p28-step-02.md")
EXAMPLE_PATH = Path("docs/operations/p28-produce-longform-output-contract-example.json")


def test_p28_step_02_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #357 after the PR merges.",
        "produce-longform",
        "CLI arguments",
        "Expected inputs",
        "Output folder structure",
        "Planned outputs",
        "Relationship to content_package.json",
        "Relationship to platform export packs",
        "Risk fields",
        "src/long_form_command_contract.py",
        "tests/integration/test_p28_step_02.py",
    ]:
        assert term in content


def test_p28_step_02_documentation_includes_required_outputs_and_example_command() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for argument in REQUIRED_CLI_ARGUMENTS:
        assert argument in content

    for output_name in REQUIRED_PRODUCE_LONGFORM_OUTPUTS:
        assert output_name in content

    for term in [
        "--content-package content_package.json",
        "--risk-report monetization_risk_report.json",
        "--source-attribution source_attribution.json",
        "--review-only true",
        "--dry-run true",
        "outputs/longform/{package_id}/",
    ]:
        assert term in content


def test_p28_step_02_documentation_preserves_out_of_scope_and_review_gates() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "render 16:9 video",
        "upload to YouTube",
        "connect YouTube Studio",
        "clear rights",
        "approve monetization",
        "approve editorial status",
        "bypass P26 or P29 gates",
        "publish_allowed: false",
        "review_required: true",
    ]:
        assert term in content


def test_build_produce_longform_contract_required_shape() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    assert contract["schema_version"] == PRODUCE_LONGFORM_SCHEMA_VERSION
    assert contract["command"] == PRODUCE_LONGFORM_COMMAND
    assert contract["status"] == "design_only_not_implemented"
    assert contract["output_directory"] == PRODUCE_LONGFORM_OUTPUT_DIRECTORY_TEMPLATE.format(
        package_id="pkg-p28-longform-neymar-2014"
    )
    assert contract["publish_allowed"] is False
    assert contract["review_required"] is True


def test_build_produce_longform_contract_cli_arguments_outputs_and_risks() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    cli_argument_names = [argument["name"] for argument in contract["cli_arguments"]]
    assert set(REQUIRED_CLI_ARGUMENTS) <= set(cli_argument_names)

    assert set(REQUIRED_PRODUCE_LONGFORM_OUTPUTS) <= set(contract["planned_outputs"])
    for output_name in REQUIRED_PRODUCE_LONGFORM_OUTPUTS:
        output = contract["planned_outputs"][output_name]
        assert output["path"].endswith(output_name)
        assert output["purpose"]
        assert output["contains"]

    assert set(REQUIRED_RISK_FIELDS) <= set(contract["risk_fields"])
    assert contract["risk_fields"]["publish_allowed"] is False
    assert contract["risk_fields"]["review_required"] is True
    assert contract["risk_fields"]["rights_review_required"] is True
    assert contract["risk_fields"]["factual_review_required"] is True
    assert contract["risk_fields"]["editorial_review_required"] is True


def test_produce_longform_contract_connections() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    content_connection = contract["content_package_connection"]
    assert content_connection["input_path"] == "content_package.json"
    assert content_connection["planned_output_path"].endswith("content_package_link.json")
    assert "content_package_path" in content_connection["required_fields"]
    assert "longform_plan_path" in content_connection["required_fields"]

    platform_connection = contract["platform_export_connection"]
    assert platform_connection["planned_output_path"].endswith("platform_export_links.json")
    assert platform_connection["direct_upload"] == "out_of_scope"
    assert "P27" in platform_connection["shorts_cutdowns"]


def test_validate_produce_longform_contract_accepts_generated_contract() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    result = validate_produce_longform_contract(contract)

    assert result["schema_version"] == "p28.produce_longform_contract_validation.v1"
    assert result["is_valid"] is True
    assert result["command"] == PRODUCE_LONGFORM_COMMAND
    assert result["required_cli_arguments_checked"] == list(REQUIRED_CLI_ARGUMENTS)
    assert result["required_outputs_checked"] == list(REQUIRED_PRODUCE_LONGFORM_OUTPUTS)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_validate_produce_longform_contract_catches_missing_output() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    del contract["planned_outputs"]["longform_plan.json"]

    result = validate_produce_longform_contract(contract)

    assert result["is_valid"] is False
    assert "missing required planned outputs" in result["errors"]


def test_validate_produce_longform_contract_catches_missing_cli_argument() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    contract["cli_arguments"] = [
        argument for argument in contract["cli_arguments"] if argument["name"] != "--review-only"
    ]
    contract["example_command"] = contract["example_command"].replace(" --review-only true", "")

    result = validate_produce_longform_contract(contract)

    assert result["is_valid"] is False
    assert "missing required CLI arguments" in result["errors"]
    assert "example command missing --review-only" in result["errors"]


def test_validate_produce_longform_contract_catches_publish_upload_regression() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    contract["publish_allowed"] = True
    contract["risk_fields"]["publish_allowed"] = True
    contract["platform_export_connection"]["direct_upload"] = "enabled"

    result = validate_produce_longform_contract(contract)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "risk publish_allowed must remain false" in result["errors"]
    assert "direct upload must remain out of scope" in result["errors"]


def test_validate_produce_longform_contract_catches_risk_regression() -> None:
    contract = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    contract["risk_fields"]["rights_review_required"] = False
    contract["risk_fields"]["factual_review_required"] = False
    contract["risk_fields"]["editorial_review_required"] = False

    result = validate_produce_longform_contract(contract)

    assert result["is_valid"] is False
    assert "rights review must be required" in result["errors"]
    assert "factual review must be required" in result["errors"]
    assert "editorial review must be required" in result["errors"]


def test_produce_longform_example_contract_is_valid() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_produce_longform_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == PRODUCE_LONGFORM_SCHEMA_VERSION
    assert example["command"] == PRODUCE_LONGFORM_COMMAND
    assert set(REQUIRED_PRODUCE_LONGFORM_OUTPUTS) <= set(example["planned_outputs"])
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_produce_longform_contract_output_is_deterministic() -> None:
    first = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    second = build_produce_longform_contract(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    assert first == second


def test_build_produce_longform_contract_validates_text_inputs() -> None:
    with pytest.raises(ValueError):
        build_produce_longform_contract("   ")

    with pytest.raises(ValueError):
        build_produce_longform_contract("Neymar comeback", package_id="   ")
