"""P32 local operator CLI and dry-run runbook contracts.

P32 defines a safe local command surface for operators. It does not implement a
live executable CLI, upload to platforms, schedule jobs, store credentials, send
notifications, sync real account data, or perform destructive cleanup.
"""

from __future__ import annotations

from typing import Any

P32_CONTRACT_VERSION = "p32.local_operator_cli.v1"
P32_VALIDATION_VERSION = "p32.local_operator_cli_validation.v1"

COMMANDS = (
    "validate-package",
    "review-readiness",
    "build-report",
    "export-handoff",
    "dry-run-publish-check",
    "closeout-check",
)

COMMAND_FIELDS = (
    "command_name",
    "purpose",
    "required_inputs",
    "outputs",
    "allowed_modes",
    "safety_flags",
)

DRY_RUN_FLAGS = (
    "dry_run",
    "no_network",
    "no_upload",
    "no_scheduler",
    "no_credentials",
    "no_external_notifications",
    "read_only_inputs",
)

ALLOWED_MODES = (
    "inspect",
    "validate",
    "build-local-artifact",
    "package-local-handoff",
)

BLOCKED_MODES = (
    "upload",
    "publish",
    "schedule",
    "notify",
    "delete",
    "sync-account",
)

ARTIFACT_FIELDS = (
    "command_name",
    "input_artifacts",
    "output_artifacts",
    "required_paths",
    "optional_paths",
    "generated_manifest",
    "operator_summary",
    "validation_report",
)

EXIT_CODES = {
    "success": 0,
    "validation_failure": 1,
    "governance_block": 2,
    "missing_artifact": 3,
    "unsafe_mode_request": 4,
    "internal_error": 5,
}

WARNING_CATEGORIES = (
    "missing_optional_artifact",
    "stale_input",
    "review_required",
    "risk_warning",
    "export_warning",
)

BLOCKING_CATEGORIES = (
    "publish_block",
    "rights_block",
    "unsafe_mode_block",
    "credential_request_block",
)

RUNBOOK_STEPS = (
    "collect_inputs",
    "run_validation",
    "review_warnings",
    "resolve_blockers",
    "build_report",
    "prepare_handoff",
    "record_decision",
)

HANDOFF_CHECKLIST_ITEMS = (
    "artifacts_included",
    "warnings_reviewed",
    "blockers_resolved_or_documented",
    "review_owner_assigned",
    "no_external_action_performed",
)


def _safety_flags() -> dict[str, bool]:
    return {
        "dry_run": True,
        "no_network": True,
        "no_upload": True,
        "no_scheduler": True,
        "no_credentials": True,
        "no_external_notifications": True,
        "read_only_inputs": True,
    }


def _command(command_name: str, purpose: str, inputs: list[str], outputs: list[str], allowed_modes: list[str]) -> dict[str, Any]:
    return {
        "command_name": command_name,
        "purpose": purpose,
        "required_inputs": inputs,
        "outputs": outputs,
        "allowed_modes": allowed_modes,
        "safety_flags": _safety_flags(),
    }


def build_p32_local_operator_cli_contract() -> dict[str, Any]:
    """Build the deterministic P32 local operator CLI contract."""

    command_registry = [
        _command(
            "validate-package",
            "Validate package structure, required metadata, and local artifact references.",
            ["content_package_path"],
            ["validation_report.json"],
            ["inspect", "validate"],
        ),
        _command(
            "review-readiness",
            "Check P29 publish-readiness and governance state without exporting or uploading.",
            ["publish_readiness_manifest_path", "editorial_status_path"],
            ["readiness_review.json", "operator_summary.md"],
            ["inspect", "validate"],
        ),
        _command(
            "build-report",
            "Build a local operator report from P31 reporting inputs.",
            ["reporting_input_bundle_path"],
            ["weekly_brief.json", "decision_queue.json", "governance_exceptions.json"],
            ["build-local-artifact"],
        ),
        _command(
            "export-handoff",
            "Package local handoff artifacts for human review only.",
            ["operator_report_package_path"],
            ["operator_handoff_manifest.json", "operator_summary.md"],
            ["package-local-handoff"],
        ),
        _command(
            "dry-run-publish-check",
            "Confirm whether a package would be blocked from publish/export readiness without publishing.",
            ["publish_readiness_manifest_path", "risk_report_path"],
            ["dry_run_publish_check.json"],
            ["inspect", "validate"],
        ),
        _command(
            "closeout-check",
            "Validate closeout checklist artifacts for the current batch or epic.",
            ["closeout_checklist_path"],
            ["closeout_validation_report.json"],
            ["inspect", "validate"],
        ),
    ]

    artifact_contract = [
        {
            "command_name": command["command_name"],
            "input_artifacts": command["required_inputs"],
            "output_artifacts": command["outputs"],
            "required_paths": command["required_inputs"],
            "optional_paths": ["operator_notes_path", "manual_override_notes_path"],
            "generated_manifest": f"{command['command_name']}_manifest.json",
            "operator_summary": "operator_summary.md",
            "validation_report": f"{command['command_name']}_validation_report.json",
            "local_only": True,
            "external_upload": False,
        }
        for command in command_registry
    ]

    return {
        "schema_version": P32_CONTRACT_VERSION,
        "parent_epic": 427,
        "content_type": "local_operator_cli_contract",
        "command_registry": {
            "issue": 428,
            "required_commands": list(COMMANDS),
            "required_fields": list(COMMAND_FIELDS),
            "commands": command_registry,
        },
        "dry_run_safety": {
            "issue": 429,
            "required_flags": list(DRY_RUN_FLAGS),
            "allowed_modes": list(ALLOWED_MODES),
            "blocked_modes": list(BLOCKED_MODES),
            "default_flags": _safety_flags(),
            "external_actions_allowed": False,
        },
        "artifact_contract": {
            "issue": 430,
            "required_fields": list(ARTIFACT_FIELDS),
            "artifacts": artifact_contract,
            "outputs_are_local_only": True,
        },
        "exit_code_semantics": {
            "issue": 431,
            "exit_codes": EXIT_CODES.copy(),
            "warning_categories": list(WARNING_CATEGORIES),
            "blocking_categories": list(BLOCKING_CATEGORIES),
            "fail_closed_on_unsafe_request": True,
            "examples": [
                {"case": "all_checks_pass", "exit_code": 0, "category": "success"},
                {"case": "missing_required_manifest", "exit_code": 3, "category": "missing_artifact"},
                {"case": "publish_block_active", "exit_code": 2, "category": "publish_block"},
                {"case": "operator_requested_upload", "exit_code": 4, "category": "unsafe_mode_block"},
            ],
        },
        "local_runbook": {
            "issue": 432,
            "steps": list(RUNBOOK_STEPS),
            "handoff_checklist": list(HANDOFF_CHECKLIST_ITEMS),
            "operator_rule": "Operators must not publish, upload, schedule, notify, sync accounts, or store credentials from this runbook.",
            "manual_only": True,
        },
        "closeout": {
            "issue": 433,
            "child_tasks": [428, 429, 430, 431, 432, 433],
            "no_executable_cli": True,
            "no_live_upload": True,
            "no_scheduler": True,
            "no_external_notifications": True,
            "no_credential_storage": True,
            "no_destructive_cleanup": True,
            "no_auto_publish_path": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_p32_local_operator_cli_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the P32 local operator CLI contract."""

    errors: list[str] = []
    _require(contract.get("schema_version") == P32_CONTRACT_VERSION, errors, "schema_version mismatch")
    _require(contract.get("parent_epic") == 427, errors, "parent epic must be 427")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    registry = contract.get("command_registry", {})
    _require(set(COMMANDS) <= set(registry.get("required_commands", [])), errors, "required commands missing")
    _require(set(COMMAND_FIELDS) <= set(registry.get("required_fields", [])), errors, "command fields missing")
    seen_commands = [command.get("command_name") for command in registry.get("commands", [])]
    _require(set(COMMANDS) <= set(seen_commands), errors, "command registry missing commands")
    for command in registry.get("commands", []):
        _require(set(COMMAND_FIELDS) <= set(command), errors, "command entry missing fields")
        _require(command.get("command_name") in COMMANDS, errors, "unsupported command")
        _require(command.get("safety_flags", {}).get("dry_run") is True, errors, "command must be dry-run")
        _require(command.get("safety_flags", {}).get("no_upload") is True, errors, "command must block upload")
        _require(command.get("safety_flags", {}).get("no_external_notifications") is True, errors, "command must block notifications")
        _require(not set(command.get("allowed_modes", [])) & set(BLOCKED_MODES), errors, "command allowed mode includes blocked mode")

    dry_run = contract.get("dry_run_safety", {})
    _require(set(DRY_RUN_FLAGS) <= set(dry_run.get("required_flags", [])), errors, "dry-run flags missing")
    _require(set(ALLOWED_MODES) <= set(dry_run.get("allowed_modes", [])), errors, "allowed modes missing")
    _require(set(BLOCKED_MODES) <= set(dry_run.get("blocked_modes", [])), errors, "blocked modes missing")
    for flag in DRY_RUN_FLAGS:
        _require(dry_run.get("default_flags", {}).get(flag) is True, errors, f"{flag} must default true")
    _require(dry_run.get("external_actions_allowed") is False, errors, "external actions must remain blocked")

    artifact = contract.get("artifact_contract", {})
    _require(set(ARTIFACT_FIELDS) <= set(artifact.get("required_fields", [])), errors, "artifact fields missing")
    _require(artifact.get("outputs_are_local_only") is True, errors, "outputs must remain local only")
    artifact_commands = [item.get("command_name") for item in artifact.get("artifacts", [])]
    _require(set(COMMANDS) <= set(artifact_commands), errors, "artifact map missing commands")
    for item in artifact.get("artifacts", []):
        _require(set(ARTIFACT_FIELDS) <= set(item), errors, "artifact entry missing fields")
        _require(item.get("local_only") is True, errors, "artifact must be local only")
        _require(item.get("external_upload") is False, errors, "artifact must not upload externally")

    semantics = contract.get("exit_code_semantics", {})
    exit_codes = semantics.get("exit_codes", {})
    _require(exit_codes == EXIT_CODES, errors, "exit codes mismatch")
    _require(set(WARNING_CATEGORIES) <= set(semantics.get("warning_categories", [])), errors, "warning categories missing")
    _require(set(BLOCKING_CATEGORIES) <= set(semantics.get("blocking_categories", [])), errors, "blocking categories missing")
    _require(semantics.get("fail_closed_on_unsafe_request") is True, errors, "unsafe requests must fail closed")

    runbook = contract.get("local_runbook", {})
    _require(tuple(runbook.get("steps", [])) == RUNBOOK_STEPS, errors, "runbook steps mismatch")
    _require(set(HANDOFF_CHECKLIST_ITEMS) <= set(runbook.get("handoff_checklist", [])), errors, "handoff checklist missing")
    _require("must not publish" in runbook.get("operator_rule", ""), errors, "operator no-publish rule missing")
    _require(runbook.get("manual_only") is True, errors, "runbook must remain manual only")

    closeout = contract.get("closeout", {})
    _require(closeout.get("child_tasks") == [428, 429, 430, 431, 432, 433], errors, "P32 child task list mismatch")
    _require(closeout.get("no_executable_cli") is True, errors, "executable CLI exclusion missing")
    _require(closeout.get("no_live_upload") is True, errors, "live upload exclusion missing")
    _require(closeout.get("no_scheduler") is True, errors, "scheduler exclusion missing")
    _require(closeout.get("no_external_notifications") is True, errors, "external notification exclusion missing")
    _require(closeout.get("no_credential_storage") is True, errors, "credential storage exclusion missing")
    _require(closeout.get("no_destructive_cleanup") is True, errors, "destructive cleanup exclusion missing")
    _require(closeout.get("no_auto_publish_path") is True, errors, "auto-publish exclusion missing")

    return {
        "schema_version": P32_VALIDATION_VERSION,
        "is_valid": not errors,
        "commands_checked": list(COMMANDS),
        "dry_run_flags_checked": list(DRY_RUN_FLAGS),
        "artifact_fields_checked": list(ARTIFACT_FIELDS),
        "warning_categories_checked": list(WARNING_CATEGORIES),
        "blocking_categories_checked": list(BLOCKING_CATEGORIES),
        "runbook_steps_checked": list(RUNBOOK_STEPS),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
