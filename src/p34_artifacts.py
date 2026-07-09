"""P34 local artifact writer and filesystem sandbox.

P34 materializes dry-run review artifacts under an explicit allowed output root.
It never uploads, syncs cloud storage, calls networks, schedules jobs, stores
credentials, performs destructive cleanup, edits platforms, or publishes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

P34_CONTRACT_VERSION = "p34.local_artifact_writer.v1"
P34_MANIFEST_VERSION = "p34.materialized_output_manifest.v1"

GUARDRAILS = {
    "local_only": True,
    "external_upload": False,
    "cloud_sync": False,
    "network_called": False,
    "scheduler_used": False,
    "credentials_used": False,
    "destructive_cleanup_performed": False,
    "platform_edit_performed": False,
    "publish_allowed": False,
    "review_required": True,
}


def _blocked(reason: str, artifact_name: str | None = None) -> dict[str, Any]:
    return {
        "status": "blocked",
        "reason": reason,
        "artifact_name": artifact_name,
        **GUARDRAILS,
    }


def _is_url_like(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.scheme in {"http", "https", "file", "s3", "gs"}))


def validate_artifact_path(output_root: str | Path, artifact_name: str) -> dict[str, Any]:
    """Validate and resolve a local artifact path under output_root only."""

    if not artifact_name or artifact_name.strip() != artifact_name:
        return _blocked("artifact name is empty or padded", artifact_name)
    if artifact_name.startswith("~"):
        return _blocked("home expansion is not allowed", artifact_name)
    if _is_url_like(artifact_name):
        return _blocked("URL-like paths are not allowed", artifact_name)
    if "\\" in artifact_name:
        return _blocked("backslash path separators are not allowed", artifact_name)

    candidate = Path(artifact_name)
    if candidate.is_absolute():
        return _blocked("absolute paths are not allowed", artifact_name)
    if any(part in {"..", ""} for part in candidate.parts):
        return _blocked("parent traversal or empty path segments are not allowed", artifact_name)

    root = Path(output_root).expanduser().resolve(strict=False)
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return _blocked("resolved path escapes output root", artifact_name)

    return {
        "status": "allowed",
        "artifact_name": artifact_name,
        "output_root": str(root),
        "resolved_path": str(resolved),
        **GUARDRAILS,
    }


def _write_text(output_root: str | Path, artifact_name: str, content: str, *, allow_overwrite: bool = False) -> dict[str, Any]:
    validation = validate_artifact_path(output_root, artifact_name)
    if validation["status"] != "allowed":
        return validation

    path = Path(validation["resolved_path"])
    if path.exists() and not allow_overwrite:
        return _blocked("target exists and overwrite is not allowed", artifact_name)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "status": "written",
        "artifact_name": artifact_name,
        "path": str(path),
        "bytes": len(content.encode("utf-8")),
        "allow_overwrite": allow_overwrite,
        **GUARDRAILS,
    }


def write_json_artifact(output_root: str | Path, artifact_name: str, payload: dict[str, Any], *, allow_overwrite: bool = False) -> dict[str, Any]:
    """Write deterministic local JSON under the allowed output root."""

    content = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    result = _write_text(output_root, artifact_name, content, allow_overwrite=allow_overwrite)
    if result["status"] == "written":
        result["content_type"] = "application/json"
    return result


def build_operator_summary(result_payload: dict[str, Any]) -> str:
    """Build a local Markdown operator summary from a P33-style result payload."""

    command = result_payload.get("command_name", "unknown")
    status = result_payload.get("status", "unknown")
    warnings = result_payload.get("warnings", []) or []
    blockers = result_payload.get("blockers", []) or []
    planned_outputs = result_payload.get("planned_outputs", []) or []
    lines = [
        f"# Operator Summary — {command}",
        "",
        f"Status: `{status}`",
        f"Mode: `{result_payload.get('mode', 'unknown')}`",
        "",
        "## Planned outputs",
    ]
    lines.extend(f"- `{item}`" for item in planned_outputs) if planned_outputs else lines.append("- None")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- None")
    lines.extend(["", "## Blockers"])
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- None")
    lines.extend(
        [
            "",
            "## Guardrails",
            "- Local-only review artifact.",
            "- No external upload, cloud sync, network call, scheduler, credential storage, destructive cleanup, platform edit, or publishing action was performed.",
            "- Human review remains required.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_operator_summary(output_root: str | Path, artifact_name: str, result_payload: dict[str, Any], *, allow_overwrite: bool = False) -> dict[str, Any]:
    result = _write_text(output_root, artifact_name, build_operator_summary(result_payload), allow_overwrite=allow_overwrite)
    if result["status"] == "written":
        result["content_type"] = "text/markdown"
    return result


def build_materialized_manifest(command_name: str, output_root: str | Path, written_files: list[dict[str, Any]], blocked_files: list[dict[str, Any]], *, created_at: str = "manual") -> dict[str, Any]:
    """Build a local-only manifest for materialized outputs."""

    return {
        "schema_version": P34_MANIFEST_VERSION,
        "command_name": command_name,
        "output_root": str(Path(output_root).expanduser().resolve(strict=False)),
        "written_files": written_files,
        "blocked_files": blocked_files,
        "warnings": [item["reason"] for item in blocked_files if item.get("reason")],
        "created_at": created_at,
        **GUARDRAILS,
    }


def materialize_command_result(output_root: str | Path, result_payload: dict[str, Any], *, allow_overwrite: bool = False, created_at: str = "manual") -> dict[str, Any]:
    """Write JSON, Markdown summary, and manifest for a P33 command result."""

    command_name = result_payload.get("command_name", "unknown")
    base_name = command_name.replace(" ", "-")
    written: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for result in [
        write_json_artifact(output_root, f"{base_name}/result.json", result_payload, allow_overwrite=allow_overwrite),
        write_operator_summary(output_root, f"{base_name}/operator_summary.md", result_payload, allow_overwrite=allow_overwrite),
    ]:
        (written if result["status"] == "written" else blocked).append(result)

    manifest = build_materialized_manifest(command_name, output_root, written, blocked, created_at=created_at)
    manifest_result = write_json_artifact(output_root, f"{base_name}/manifest.json", manifest, allow_overwrite=allow_overwrite)
    (written if manifest_result["status"] == "written" else blocked).append(manifest_result)
    manifest["written_files"] = written
    manifest["blocked_files"] = blocked
    manifest["warnings"] = [item["reason"] for item in blocked if item.get("reason")]
    return manifest
