"""P35 local artifact integrity and retention metadata.

P35 adds checksum, inventory, retention, verification, and drift-report helpers
for local artifacts. It never deletes, moves, uploads, syncs, calls networks,
schedules jobs, stores credentials, edits platforms, or publishes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

P35_CONTRACT_VERSION = "p35.local_artifact_integrity.v1"
P35_INVENTORY_VERSION = "p35.artifact_inventory.v1"
P35_RETENTION_VERSION = "p35.retention_policy.v1"
P35_VERIFICATION_VERSION = "p35.integrity_verification.v1"
P35_DRIFT_REPORT_VERSION = "p35.drift_warning_report.v1"

RETENTION_CLASSES = ("keep", "review_later", "archive_candidate", "legal_hold")
VERIFICATION_STATUSES = ("match", "missing", "changed", "unexpected")

GUARDRAILS = {
    "local_only": True,
    "deletion_performed": False,
    "moving_performed": False,
    "cloud_sync": False,
    "external_upload": False,
    "network_called": False,
    "scheduler_used": False,
    "credentials_used": False,
    "platform_edit_performed": False,
    "publish_allowed": False,
    "review_required": True,
}


def _bytes_for_payload(payload: str | bytes | dict[str, Any] | list[Any]) -> tuple[bytes, str]:
    if isinstance(payload, bytes):
        return payload, "application/octet-stream"
    if isinstance(payload, str):
        return payload.encode("utf-8"), "text/plain"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return encoded, "application/json"


def checksum_payload(payload: str | bytes | dict[str, Any] | list[Any], *, generated_at: str = "manual") -> dict[str, Any]:
    """Create deterministic sha256 checksum metadata for local payload content."""

    payload_bytes, content_type = _bytes_for_payload(payload)
    return {
        "algorithm": "sha256",
        "digest": hashlib.sha256(payload_bytes).hexdigest(),
        "byte_count": len(payload_bytes),
        "content_type": content_type,
        "generated_at": generated_at,
        **GUARDRAILS,
    }


def build_inventory_entry(
    artifact_name: str,
    relative_path: str,
    payload: str | bytes | dict[str, Any] | list[Any],
    *,
    source_command: str,
    generated_at: str = "manual",
) -> dict[str, Any]:
    checksum = checksum_payload(payload, generated_at=generated_at)
    return {
        "artifact_name": artifact_name,
        "relative_path": relative_path,
        "checksum": checksum,
        "byte_count": checksum["byte_count"],
        "content_type": checksum["content_type"],
        "source_command": source_command,
        **GUARDRAILS,
    }


def build_inventory(
    entries: list[dict[str, Any]],
    *,
    inventory_id: str,
    generated_at: str = "manual",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    ordered = sorted(entries, key=lambda item: item["relative_path"])
    return {
        "schema_version": P35_INVENTORY_VERSION,
        "inventory_id": inventory_id,
        "generated_at": generated_at,
        "entries": ordered,
        "warnings": warnings or [],
        "guardrails": GUARDRAILS.copy(),
        **GUARDRAILS,
    }


def build_retention_policy(
    policy_id: str,
    retention_class: str,
    *,
    review_after_days: int,
    owner_role: str,
    reason: str,
) -> dict[str, Any]:
    if retention_class not in RETENTION_CLASSES:
        raise ValueError(f"Unsupported retention class: {retention_class}")
    return {
        "schema_version": P35_RETENTION_VERSION,
        "policy_id": policy_id,
        "retention_class": retention_class,
        "review_after_days": review_after_days,
        "owner_role": owner_role,
        "reason": reason,
        "deletion_allowed": False,
        "manual_review_required": True,
        **GUARDRAILS,
    }


def verify_inventory(
    inventory: dict[str, Any],
    observed_entries: list[dict[str, Any]],
    *,
    generated_at: str = "manual",
) -> dict[str, Any]:
    """Compare expected and observed inventory metadata without modifying files."""

    expected_by_path = {entry["relative_path"]: entry for entry in inventory.get("entries", [])}
    observed_by_path = {entry["relative_path"]: entry for entry in observed_entries}
    results: list[dict[str, Any]] = []

    for path, expected in sorted(expected_by_path.items()):
        observed = observed_by_path.get(path)
        if observed is None:
            status = "missing"
            observed_digest = None
        else:
            observed_digest = observed.get("checksum", {}).get("digest")
            status = "match" if observed_digest == expected.get("checksum", {}).get("digest") else "changed"
        results.append(
            {
                "relative_path": path,
                "status": status,
                "expected_digest": expected.get("checksum", {}).get("digest"),
                "observed_digest": observed_digest,
            }
        )

    for path, observed in sorted(observed_by_path.items()):
        if path not in expected_by_path:
            results.append(
                {
                    "relative_path": path,
                    "status": "unexpected",
                    "expected_digest": None,
                    "observed_digest": observed.get("checksum", {}).get("digest"),
                }
            )

    counts = {status: sum(1 for item in results if item["status"] == status) for status in VERIFICATION_STATUSES}
    return {
        "schema_version": P35_VERIFICATION_VERSION,
        "inventory_id": inventory.get("inventory_id"),
        "generated_at": generated_at,
        "results": results,
        "counts": counts,
        "warnings": [item["status"] for item in results if item["status"] != "match"],
        **GUARDRAILS,
    }


def build_drift_report(
    verification: dict[str, Any],
    retention_policies: list[dict[str, Any]],
    *,
    generated_at: str = "manual",
) -> dict[str, Any]:
    warnings: list[str] = []
    counts = verification.get("counts", {})
    for status in ("missing", "changed", "unexpected"):
        if counts.get(status, 0):
            warnings.append(f"{status}_artifacts_detected")
    for policy in retention_policies:
        if policy.get("manual_review_required"):
            warnings.append(f"manual_review_required:{policy.get('policy_id')}")
        if policy.get("retention_class") in {"review_later", "archive_candidate"}:
            warnings.append(f"retention_review_required:{policy.get('policy_id')}")

    return {
        "schema_version": P35_DRIFT_REPORT_VERSION,
        "generated_at": generated_at,
        "inventory_id": verification.get("inventory_id"),
        "verification_counts": counts,
        "warnings": warnings,
        "next_operator_steps": [
            "Review missing, changed, or unexpected artifacts manually.",
            "Confirm retention policy owner and review date.",
            "Do not delete, move, upload, sync, or publish from this report.",
        ],
        "cleanup_performed": False,
        "external_action_performed": False,
        **GUARDRAILS,
    }
