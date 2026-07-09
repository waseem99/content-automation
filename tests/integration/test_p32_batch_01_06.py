from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p32_cli import (
    ALLOWED_MODES,
    ARTIFACT_FIELDS,
    BLOCKED_MODES,
    BLOCKING_CATEGORIES,
    COMMANDS,
    DRY_RUN_FLAGS,
    EXIT_CODES,
    HANDOFF_CHECKLIST_ITEMS,
    RUNBOOK_STEPS,
    WARNING_CATEGORIES,
    build_p32_local_operator_cli_contract,
    validate_p32_local_operator_cli_contract,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p32-local-operator-cli-example.json")
CHECKLIST_PATH = Path("docs/operations/p32-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p32-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p32-step-01.md"),
    Path("docs/operations/p32-step-02.md"),
    Path("docs/operations/p32-step-03.md"),
    Path("docs/operations/p32-step-04.md"),
    Path("docs/operations/p32-step-05.md"),
    Path("docs/operations/p32-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p32_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p32-step-01.md": ["Closes #428", "local operator command registry", "No command uploads"],
        "docs/operations/p32-step-02.md": ["Closes #429", "dry-run execution", "Unsafe modes must fail closed"],
        "docs/operations/p32-step-03.md": ["Closes #430", "input and output artifact contract", "local/review-only"],
        "docs/operations/p32-step-04.md": ["Closes #431", "exit-code semantics", "unsafe_mode_request"],
        "docs/operations/p32-step-05.md": ["Closes #432", "local operator runbook", "Operators must not publish"],
        "docs/operations/p32-step-06.md": ["Closes #433", "P32", "no auto-publish path"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_generated_p32_contract_is_valid() -> None:
    contract = build_p32_local_operator_cli_contract()
    result = validate_p32_local_operator_cli_contract(contract)

    assert result["schema_version"] == "p32.local_operator_cli_validation.v1"
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["commands_checked"] == list(COMMANDS)
    assert result["dry_run_flags_checked"] == list(DRY_RUN_FLAGS)
    assert result["artifact_fields_checked"] == list(ARTIFACT_FIELDS)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True


def test_p32_example_contract_is_valid() -> None:
    example = _read_json(EXAMPLE_PATH)
    result = validate_p32_local_operator_cli_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == "p32.local_operator_cli.v1"
    assert example["parent_epic"] == 427
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_p32_command_registry_has_required_commands_and_safety_flags() -> None:
    contract = build_p32_local_operator_cli_contract()
    registry = contract["command_registry"]

    assert set(COMMANDS) <= set(registry["required_commands"])
    seen_commands = {command["command_name"] for command in registry["commands"]}
    assert set(COMMANDS) <= seen_commands
    for command in registry["commands"]:
        assert command["safety_flags"]["dry_run"] is True
        assert command["safety_flags"]["no_upload"] is True
        assert command["safety_flags"]["no_external_notifications"] is True
        assert not set(command["allowed_modes"]) & set(BLOCKED_MODES)


def test_p32_dry_run_safety_blocks_unsafe_modes() -> None:
    contract = build_p32_local_operator_cli_contract()
    dry_run = contract["dry_run_safety"]

    assert set(DRY_RUN_FLAGS) <= set(dry_run["required_flags"])
    assert set(ALLOWED_MODES) <= set(dry_run["allowed_modes"])
    assert set(BLOCKED_MODES) <= set(dry_run["blocked_modes"])
    for flag in DRY_RUN_FLAGS:
        assert dry_run["default_flags"][flag] is True
    assert dry_run["external_actions_allowed"] is False


def test_p32_artifact_contract_is_local_only_for_all_commands() -> None:
    contract = build_p32_local_operator_cli_contract()
    artifact = contract["artifact_contract"]

    assert set(ARTIFACT_FIELDS) <= set(artifact["required_fields"])
    assert artifact["outputs_are_local_only"] is True
    seen = {item["command_name"] for item in artifact["artifacts"]}
    assert set(COMMANDS) <= seen
    for item in artifact["artifacts"]:
        assert set(ARTIFACT_FIELDS) <= set(item)
        assert item["local_only"] is True
        assert item["external_upload"] is False


def test_p32_exit_code_semantics_and_categories_are_complete() -> None:
    contract = build_p32_local_operator_cli_contract()
    semantics = contract["exit_code_semantics"]

    assert semantics["exit_codes"] == EXIT_CODES
    assert set(WARNING_CATEGORIES) <= set(semantics["warning_categories"])
    assert set(BLOCKING_CATEGORIES) <= set(semantics["blocking_categories"])
    assert semantics["fail_closed_on_unsafe_request"] is True
    example_cases = {example["case"] for example in semantics["examples"]}
    assert "operator_requested_upload" in example_cases


def test_p32_runbook_and_handoff_checklist_are_complete() -> None:
    contract = build_p32_local_operator_cli_contract()
    runbook = contract["local_runbook"]

    assert runbook["steps"] == list(RUNBOOK_STEPS)
    assert set(HANDOFF_CHECKLIST_ITEMS) <= set(runbook["handoff_checklist"])
    assert "must not publish" in runbook["operator_rule"]
    assert runbook["manual_only"] is True


def test_p32_validation_catches_upload_and_notification_regressions() -> None:
    contract = build_p32_local_operator_cli_contract()
    contract["command_registry"]["commands"][0]["safety_flags"]["no_upload"] = False
    contract["command_registry"]["commands"][0]["safety_flags"]["no_external_notifications"] = False
    contract["artifact_contract"]["artifacts"][0]["external_upload"] = True

    result = validate_p32_local_operator_cli_contract(contract)

    assert result["is_valid"] is False
    assert "command must block upload" in result["errors"]
    assert "command must block notifications" in result["errors"]
    assert "artifact must not upload externally" in result["errors"]


def test_p32_validation_catches_unsafe_mode_regression() -> None:
    contract = build_p32_local_operator_cli_contract()
    contract["command_registry"]["commands"][0]["allowed_modes"].append("publish")
    contract["dry_run_safety"]["external_actions_allowed"] = True
    contract["exit_code_semantics"]["fail_closed_on_unsafe_request"] = False

    result = validate_p32_local_operator_cli_contract(contract)

    assert result["is_valid"] is False
    assert "command allowed mode includes blocked mode" in result["errors"]
    assert "external actions must remain blocked" in result["errors"]
    assert "unsafe requests must fail closed" in result["errors"]


def test_p32_closeout_report_and_checklist_cover_guardrails() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    checklist = _read_json(CHECKLIST_PATH)

    for issue in ["#428", "#429", "#430", "#431", "#432", "#433"]:
        assert issue in report

    for guardrail in [
        "No executable CLI runtime.",
        "No live platform uploads.",
        "No schedulers or background jobs.",
        "No OAuth or credential storage.",
        "No real account sync.",
        "No external notifications.",
        "No destructive filesystem cleanup.",
        "No auto-publish path.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]

    assert [task["issue"] for task in checklist["child_tasks"]] == [428, 429, 430, 431, 432, 433]
    assert checklist["no_executable_cli"] is True
    assert checklist["no_live_upload"] is True
    assert checklist["no_scheduler"] is True
    assert checklist["no_external_notifications"] is True
    assert checklist["no_credential_storage"] is True
    assert checklist["no_destructive_cleanup"] is True
    assert checklist["no_auto_publish_path"] is True


def test_p32_contract_output_is_deterministic() -> None:
    assert build_p32_local_operator_cli_contract() == build_p32_local_operator_cli_contract()
