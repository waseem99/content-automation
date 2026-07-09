"""P36 local review packet builder and index.

P36 assembles local metadata for human-review packets using prior local artifacts,
reports, command results, and inventories. It never zips, uploads, emails,
syncs, calls networks, schedules jobs, stores credentials, edits platforms,
deletes, moves, or publishes.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

P36_CONTRACT_VERSION = "p36.local_review_packet.v1"
P36_HANDOFF_VERSION = "p36.local_review_handoff.v1"

ITEM_TYPES = ("report", "cli_result", "artifact", "inventory", "summary", "blocker_appendix", "checklist")
SECTIONS = ("executive_summary", "review_required", "ready_for_approval", "blocked", "reference_artifacts")
CHECKLIST_GATES = ("completeness", "governance", "integrity", "retention", "blocker_review", "final_operator_decision")
DECISION_OPTIONS = ("approve_local_packet", "request_changes", "hold_blocked", "archive_candidate_review")
BLOCKER_TYPES = ("governance_block", "integrity_drift", "retention_review", "missing_artifact", "rights_review", "unsafe_publish_state")
SEVERITIES = ("low", "medium", "high", "critical")

GUARDRAILS = {
    "local_only": True,
    "zip_created": False,
    "email_sent": False,
    "slack_sent": False,
    "cloud_sync": False,
    "external_upload": False,
    "network_called": False,
    "scheduler_used": False,
    "credentials_used": False,
    "platform_edit_performed": False,
    "deletion_performed": False,
    "moving_performed": False,
    "publish_allowed": False,
    "review_required": True,
}


def build_packet_item(
    item_id: str,
    title: str,
    relative_path: str,
    item_type: str,
    *,
    source_system: str,
    source_issue: int,
    review_status: str,
    reviewer_role: str,
    required: bool,
    checksum_digest: str | None = None,
    section: str = "reference_artifacts",
) -> dict[str, Any]:
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Unsupported item type: {item_type}")
    if section not in SECTIONS:
        raise ValueError(f"Unsupported section: {section}")
    return {
        "item_id": item_id,
        "title": title,
        "relative_path": relative_path,
        "item_type": item_type,
        "section": section,
        "source_system": source_system,
        "source_issue": source_issue,
        "review_status": review_status,
        "reviewer_role": reviewer_role,
        "required": required,
        "checksum_digest": checksum_digest,
        **GUARDRAILS,
    }


def build_packet_index(
    packet_id: str,
    packet_title: str,
    items: list[dict[str, Any]],
    *,
    generated_at: str = "manual",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    ordered = sorted(items, key=lambda item: (SECTIONS.index(item["section"]), item["relative_path"], item["item_id"]))
    section_counts = {section: sum(1 for item in ordered if item["section"] == section) for section in SECTIONS}
    type_counts = dict(Counter(item["item_type"] for item in ordered))
    required_count = sum(1 for item in ordered if item.get("required"))
    return {
        "schema_version": P36_CONTRACT_VERSION,
        "packet_id": packet_id,
        "generated_at": generated_at,
        "packet_title": packet_title,
        "items": ordered,
        "sections": list(SECTIONS),
        "counts": {
            "total_items": len(ordered),
            "required_items": required_count,
            "section_counts": section_counts,
            "type_counts": type_counts,
        },
        "warnings": warnings or [],
        "guardrails": GUARDRAILS.copy(),
        **GUARDRAILS,
    }


def build_reviewer_checklist(
    checklist_id: str,
    reviewer_role: str,
    required_items: list[str],
    *,
    approval_allowed: bool = False,
) -> dict[str, Any]:
    return {
        "checklist_id": checklist_id,
        "reviewer_role": reviewer_role,
        "gates": list(CHECKLIST_GATES),
        "required_items": sorted(required_items),
        "decision_options": list(DECISION_OPTIONS),
        "review_required": True,
        "approval_allowed": approval_allowed,
        "approval_mode": "human_only_local_review",
        **GUARDRAILS,
    }


def build_blocker_appendix(
    appendix_id: str,
    blockers: list[dict[str, Any]],
    *,
    generated_at: str = "manual",
) -> dict[str, Any]:
    normalized = []
    for blocker in blockers:
        blocker_type = blocker["blocker_type"]
        severity = blocker["severity"]
        if blocker_type not in BLOCKER_TYPES:
            raise ValueError(f"Unsupported blocker type: {blocker_type}")
        if severity not in SEVERITIES:
            raise ValueError(f"Unsupported severity: {severity}")
        normalized.append({**blocker, **GUARDRAILS})
    severity_counts = {severity: sum(1 for item in normalized if item["severity"] == severity) for severity in SEVERITIES}
    type_counts = {blocker_type: sum(1 for item in normalized if item["blocker_type"] == blocker_type) for blocker_type in BLOCKER_TYPES}
    return {
        "appendix_id": appendix_id,
        "generated_at": generated_at,
        "blockers": sorted(normalized, key=lambda item: (SEVERITIES.index(item["severity"]), item["blocker_type"], item["source_item_id"])),
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "automated_remediation_performed": False,
        **GUARDRAILS,
    }


def build_local_handoff_manifest(
    manifest_id: str,
    packet: dict[str, Any],
    checklists: list[dict[str, Any]],
    blocker_appendices: list[dict[str, Any]],
    *,
    generated_at: str = "manual",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": P36_HANDOFF_VERSION,
        "manifest_id": manifest_id,
        "packet_id": packet["packet_id"],
        "generated_at": generated_at,
        "packet_files": [item["relative_path"] for item in packet.get("items", [])],
        "reviewer_roles": sorted({item["reviewer_role"] for item in packet.get("items", [])}),
        "checklist_ids": [item["checklist_id"] for item in checklists],
        "blocker_appendices": [item["appendix_id"] for item in blocker_appendices],
        "warnings": warnings or packet.get("warnings", []),
        "next_local_steps": [
            "Review packet index locally.",
            "Resolve blocker appendix items before approval.",
            "Record human decision without uploading, emailing, syncing, or publishing.",
        ],
        "distribution_status": "local_only_not_sent",
        "external_action_performed": False,
        **GUARDRAILS,
    }


def validate_review_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != P36_CONTRACT_VERSION:
        errors.append("schema_version mismatch")
    if packet.get("local_only") is not True:
        errors.append("packet must remain local only")
    for forbidden_key in ("zip_created", "email_sent", "slack_sent", "cloud_sync", "external_upload", "network_called", "scheduler_used", "credentials_used", "platform_edit_performed", "deletion_performed", "moving_performed", "publish_allowed"):
        if packet.get(forbidden_key) not in (False, None):
            errors.append(f"{forbidden_key} must remain false")
    if packet.get("review_required") is not True:
        errors.append("review_required must remain true")
    for item in packet.get("items", []):
        if item.get("item_type") not in ITEM_TYPES:
            errors.append("unsupported item type")
        if item.get("section") not in SECTIONS:
            errors.append("unsupported section")
        if item.get("local_only") is not True or item.get("publish_allowed") is not False:
            errors.append("item guardrails invalid")
    return {
        "schema_version": "p36.local_review_packet_validation.v1",
        "is_valid": not errors,
        "errors": errors,
        "items_checked": len(packet.get("items", [])),
        **GUARDRAILS,
    }
