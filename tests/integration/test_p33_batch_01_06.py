from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from src.p32_cli import BLOCKED_MODES, COMMANDS, EXIT_CODES
from src.p33_cli_runtime import (
    P33_RESULT_VERSION,
    build_command_result,
    build_parser,
    render_json,
    run_cli,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p33-cli-runtime-example.json")
CHECKLIST_PATH = Path("docs/operations/p33-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p33-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p33-step-01.md"),
    Path("docs/operations/p33-step-02.md"),
    Path("docs/operations/p33-step-03.md"),
    Path("docs/operations/p33-step-04.md"),
    Path("docs/operations/p33-step-05.md"),
    Path("docs/operations/p33-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p33_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p33-step-01.md": ["Closes #436", "argument parser", "validate-package"],
        "docs/operations/p33-step-02.md": ["Closes #437", "Unsafe requests fail closed", "--allow-upload"],
        "docs/operations/p33-step-03.md": ["Closes #438", "Result payload", "external_action_performed: false"],
        "docs/operations/p33-step-04.md": ["Closes #439", "JSON output", "unsafe_mode_request"],
        "docs/operations/p33-step-05.md": ["Closes #440", "Safe examples", "Blocked examples"],
        "docs/operations/p33-step-06.md": ["Closes #441", "P33", "no auto-publish path"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_parser_supports_all_required_commands() -> None:
    parser = build_parser()
    for command in COMMANDS:
        namespace = parser.parse_args([command, "--mode", "inspect"])
        assert namespace.command == command
        assert namespace.mode == "inspect"
        assert namespace.inputs == []


def test_run_cli_dispatches_every_supported_command_locally() -> None:
    for command in COMMANDS:
        exit_code, result = run_cli([command, "--input", "fixture.json", "--mode", "inspect"])
        assert exit_code == EXIT_CODES["success"]
        assert result["schema_version"] == P33_RESULT_VERSION
        assert result["command_name"] == command
        assert result["status"] == "success"
        assert result["external_action_performed"] is False
        assert result["network_called"] is False
        assert result["upload_performed"] is False
        assert result["scheduler_used"] is False
        assert result["credentials_used"] is False
        assert result["notification_sent"] is False
        assert result["destructive_cleanup_performed"] is False
        assert result["publish_allowed"] is False
        assert result["review_required"] is True
        assert result["planned_outputs"]


def test_blocked_modes_fail_closed_with_unsafe_mode_exit_code() -> None:
    for mode in BLOCKED_MODES:
        exit_code, result = run_cli(["validate-package", "--mode", mode])
        assert exit_code == EXIT_CODES["unsafe_mode_request"]
        assert result["status"] == "blocked"
        assert result["category"] == "unsafe_mode_request"
        assert result["external_action_performed"] is False
        assert result["publish_allowed"] is False


@pytest.mark.parametrize(
    "flag",
    [
        "--allow-network",
        "--allow-upload",
        "--allow-scheduler",
        "--allow-credentials",
        "--allow-notifications",
        "--allow-delete",
    ],
)
def test_unsafe_allow_flags_fail_closed(flag: str) -> None:
    exit_code, result = run_cli(["dry-run-publish-check", flag])

    assert exit_code == EXIT_CODES["unsafe_mode_request"]
    assert result["status"] == "blocked"
    assert result["unsafe_flags"]
    assert result["external_action_performed"] is False
    assert result["publish_allowed"] is False


def test_missing_required_inputs_maps_to_missing_artifact() -> None:
    exit_code, result = run_cli(["review-readiness", "--require-inputs"])

    assert exit_code == EXIT_CODES["missing_artifact"]
    assert result["status"] == "blocked"
    assert result["category"] == "missing_artifact"
    assert result["received_inputs"] == []
    assert result["external_action_performed"] is False


def test_build_command_result_warns_for_missing_optional_inputs() -> None:
    namespace = argparse.Namespace(
        command="build-report",
        inputs=[],
        output_dir="reports/local",
        mode="build-local-artifact",
        require_inputs=False,
        allow_network=False,
        allow_upload=False,
        allow_scheduler=False,
        allow_credentials=False,
        allow_notifications=False,
        allow_delete=False,
    )

    exit_code, result = build_command_result(namespace)

    assert exit_code == EXIT_CODES["success"]
    assert "missing_optional_input_paths" in result["warnings"]
    assert result["external_action_performed"] is False


def test_json_rendering_is_deterministic_and_parseable() -> None:
    exit_code, result = run_cli(["closeout-check", "--input", "closeout.json"])
    rendered = render_json(result)
    parsed = json.loads(rendered)

    assert exit_code == EXIT_CODES["success"]
    assert parsed == result
    assert rendered == render_json(result)
    assert "\n" in rendered


def test_invalid_arguments_return_validation_failure_without_external_action() -> None:
    exit_code, result = run_cli(["not-a-command"])

    assert exit_code == EXIT_CODES["validation_failure"]
    assert result["status"] == "blocked"
    assert result["category"] == "validation_failure"
    assert result["external_action_performed"] is False


def test_example_file_covers_safe_and_blocked_examples() -> None:
    example = _read_json(EXAMPLE_PATH)

    assert example["schema_version"] == "p33.safe_local_cli_example.v1"
    assert len(example["safe_examples"]) == len(COMMANDS)
    safe_commands = {item[0] for item in example["safe_examples"]}
    assert set(COMMANDS) <= safe_commands
    assert example["blocked_examples"]
    assert example["exit_codes"] == EXIT_CODES
    assert example["guardrails"]["no_live_upload"] is True
    assert example["guardrails"]["no_network_call"] is True
    assert example["guardrails"]["no_auto_publish_path"] is True
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_p33_closeout_report_and_checklist_cover_guardrails() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    checklist = _read_json(CHECKLIST_PATH)

    for issue in ["#436", "#437", "#438", "#439", "#440", "#441"]:
        assert issue in report

    for guardrail in [
        "No live uploads.",
        "No network calls.",
        "No schedulers or background jobs.",
        "No OAuth or credential storage.",
        "No real account sync.",
        "No external notifications.",
        "No destructive filesystem cleanup.",
        "No auto-publish path.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]

    assert [task["issue"] for task in checklist["child_tasks"]] == [436, 437, 438, 439, 440, 441]
    assert checklist["no_live_upload"] is True
    assert checklist["no_network_call"] is True
    assert checklist["no_scheduler"] is True
    assert checklist["no_credential_storage"] is True
    assert checklist["no_destructive_cleanup"] is True
    assert checklist["no_external_notifications"] is True
    assert checklist["no_account_sync"] is True
    assert checklist["no_auto_publish_path"] is True
