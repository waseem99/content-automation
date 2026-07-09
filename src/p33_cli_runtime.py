"""P33 safe local CLI runtime.

This module implements a deterministic, dry-run-only wrapper around the P32
local operator command contract. It never calls networks, uploads files,
schedules jobs, stores credentials, sends notifications, syncs accounts, deletes
files, or publishes content.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from src.p32_cli import (
    ALLOWED_MODES,
    BLOCKED_MODES,
    COMMANDS,
    DRY_RUN_FLAGS,
    EXIT_CODES,
    _safety_flags,
    build_p32_local_operator_cli_contract,
)

P33_RUNTIME_VERSION = "p33.safe_local_cli_runtime.v1"
P33_RESULT_VERSION = "p33.safe_local_cli_result.v1"
UNSAFE_FLAG_NAMES = (
    "allow_network",
    "allow_upload",
    "allow_scheduler",
    "allow_credentials",
    "allow_notifications",
    "allow_delete",
)


def build_parser() -> argparse.ArgumentParser:
    """Create the safe local CLI parser without executing any command."""

    parser = argparse.ArgumentParser(prog="p33-local", description="Safe dry-run local operator command wrapper")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--input", action="append", default=[], dest="inputs", help="Local input artifact path; may be repeated")
    parser.add_argument("--output-dir", default="reports/local", help="Local output directory for planned artifacts")
    parser.add_argument("--mode", default="inspect", choices=tuple(ALLOWED_MODES) + tuple(BLOCKED_MODES))
    parser.add_argument("--require-inputs", action="store_true", help="Fail if the command receives no input paths")
    for flag_name in UNSAFE_FLAG_NAMES:
        parser.add_argument(f"--{flag_name.replace('_', '-')}", action="store_true", dest=flag_name)
    return parser


def _command_contract(command_name: str) -> dict[str, Any]:
    contract = build_p32_local_operator_cli_contract()
    for command in contract["command_registry"]["commands"]:
        if command["command_name"] == command_name:
            return command
    raise ValueError(f"Unsupported command: {command_name}")


def _artifact_contract(command_name: str) -> dict[str, Any]:
    contract = build_p32_local_operator_cli_contract()
    for artifact in contract["artifact_contract"]["artifacts"]:
        if artifact["command_name"] == command_name:
            return artifact
    raise ValueError(f"Unsupported artifact command: {command_name}")


def _unsafe_flags(namespace: argparse.Namespace) -> list[str]:
    return [flag_name for flag_name in UNSAFE_FLAG_NAMES if getattr(namespace, flag_name, False)]


def _blocked_result(command_name: str, mode: str, reason: str, unsafe_flags: list[str] | None = None) -> tuple[int, dict[str, Any]]:
    return EXIT_CODES["unsafe_mode_request"], {
        "schema_version": P33_RESULT_VERSION,
        "command_name": command_name,
        "mode": mode,
        "status": "blocked",
        "category": "unsafe_mode_request",
        "reason": reason,
        "unsafe_flags": unsafe_flags or [],
        "safety_flags": _safety_flags(),
        "external_action_performed": False,
        "publish_allowed": False,
        "review_required": True,
    }


def validate_safety(namespace: argparse.Namespace) -> tuple[bool, tuple[int, dict[str, Any]] | None]:
    """Validate dry-run safety before local command dispatch."""

    command_name = namespace.command
    mode = namespace.mode
    if mode in BLOCKED_MODES:
        return False, _blocked_result(command_name, mode, f"Blocked mode requested: {mode}")
    unsafe_flags = _unsafe_flags(namespace)
    if unsafe_flags:
        return False, _blocked_result(command_name, mode, "Unsafe allow-* flag requested", unsafe_flags)
    return True, None


def build_command_result(namespace: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Build a deterministic local-only command result."""

    safe, blocked = validate_safety(namespace)
    if not safe and blocked is not None:
        return blocked

    command = _command_contract(namespace.command)
    artifact = _artifact_contract(namespace.command)
    if namespace.require_inputs and not namespace.inputs:
        return EXIT_CODES["missing_artifact"], {
            "schema_version": P33_RESULT_VERSION,
            "command_name": namespace.command,
            "mode": namespace.mode,
            "status": "blocked",
            "category": "missing_artifact",
            "reason": "At least one --input path is required for this dry run.",
            "required_inputs": command["required_inputs"],
            "received_inputs": [],
            "safety_flags": _safety_flags(),
            "external_action_performed": False,
            "publish_allowed": False,
            "review_required": True,
        }

    planned_outputs = [f"{namespace.output_dir.rstrip('/')}/{output}" for output in command["outputs"]]
    planned_outputs.extend(
        [
            f"{namespace.output_dir.rstrip('/')}/{artifact['generated_manifest']}",
            f"{namespace.output_dir.rstrip('/')}/{artifact['validation_report']}",
        ]
    )

    warnings: list[str] = []
    if not namespace.inputs:
        warnings.append("missing_optional_input_paths")
    if namespace.mode not in command["allowed_modes"]:
        warnings.append("mode_allowed_by_runtime_but_not_preferred_for_command")

    result = {
        "schema_version": P33_RESULT_VERSION,
        "runtime_version": P33_RUNTIME_VERSION,
        "command_name": namespace.command,
        "mode": namespace.mode,
        "status": "success",
        "category": "success",
        "inputs": list(namespace.inputs),
        "required_inputs": command["required_inputs"],
        "output_dir": namespace.output_dir,
        "planned_outputs": planned_outputs,
        "safety_flags": _safety_flags(),
        "warnings": warnings,
        "blockers": [],
        "summary": f"Dry-run local command {namespace.command} completed without external action.",
        "external_action_performed": False,
        "network_called": False,
        "upload_performed": False,
        "scheduler_used": False,
        "credentials_used": False,
        "notification_sent": False,
        "destructive_cleanup_performed": False,
        "publish_allowed": False,
        "review_required": True,
    }
    return EXIT_CODES["success"], result


def run_cli(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    """Parse argv and run the safe local command dispatcher."""

    parser = build_parser()
    try:
        namespace = parser.parse_args(list(argv))
    except SystemExit as exc:
        return EXIT_CODES["validation_failure"], {
            "schema_version": P33_RESULT_VERSION,
            "status": "blocked",
            "category": "validation_failure",
            "reason": "Invalid CLI arguments.",
            "argparse_exit_code": int(exc.code),
            "external_action_performed": False,
            "publish_allowed": False,
            "review_required": True,
        }
    return build_command_result(namespace)


def render_json(result: dict[str, Any]) -> str:
    """Render deterministic JSON output for the local CLI result."""

    return json.dumps(result, sort_keys=True, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI-style entry point that only prints local JSON and returns an exit code."""

    exit_code, result = run_cli(argv or [])
    print(render_json(result))
    return exit_code
