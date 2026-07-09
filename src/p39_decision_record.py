"""P39 local reviewer decision records."""

from __future__ import annotations

from typing import Any

P39_DECISION_VERSION = "p39.local_decision_record.v1"
P39_STATES = ("approved_local", "request_changes", "hold_blocked", "archive_candidate_review")
FOLLOWUP_REQUIRED = {"request_changes", "hold_blocked"}

GUARDRAILS = {
    "local_only": True,
    "automated_approval_performed": False,
    "external_delivery_performed": False,
    "external_upload": False,
    "cloud_sync": False,
    "network_called": False,
    "scheduler_used": False,
    "credentials_used": False,
    "platform_edit_performed": False,
    "deletion_performed": False,
    "moving_performed": False,
    "publish_allowed": False,
    "review_required": True,
}


def validate_decision_state(decision_state: str) -> dict[str, Any]:
    return {"is_valid": decision_state in P39_STATES, "decision_state": decision_state, "supported_states": list(P39_STATES), **GUARDRAILS}


def build_signoff_metadata(reviewer_role: str, *, signoff_name: str = "TBD", decided_at: str = "manual") -> dict[str, Any]:
    return {"reviewer_role": reviewer_role, "signoff_name": signoff_name, "decided_at": decided_at, "manual_review_required": True, "digital_signature_performed": False, **GUARDRAILS}


def build_decision_record(packet_id: str, reviewer_role: str, decision_state: str, rationale: str, follow_ups: list[str] | None = None, *, decided_at: str = "manual", signoff_name: str = "TBD") -> dict[str, Any]:
    validation = validate_decision_state(decision_state)
    if not validation["is_valid"]:
        raise ValueError(f"Unsupported decision state: {decision_state}")
    follow_ups = follow_ups or []
    if decision_state in FOLLOWUP_REQUIRED and not follow_ups:
        raise ValueError(f"Follow-ups are required for {decision_state}")
    return {
        "schema_version": P39_DECISION_VERSION,
        "packet_id": packet_id,
        "reviewer_role": reviewer_role,
        "decision_state": decision_state,
        "rationale": rationale,
        "follow_ups": follow_ups,
        "follow_up_required": decision_state in FOLLOWUP_REQUIRED,
        "signoff": build_signoff_metadata(reviewer_role, signoff_name=signoff_name, decided_at=decided_at),
        "decided_at": decided_at,
        **GUARDRAILS,
    }


def render_follow_up_actions(record: dict[str, Any]) -> str:
    lines = ["# Required Follow-up Actions", ""]
    items = record.get("follow_ups", [])
    lines.extend(f"- {item}" for item in items) if items else lines.append("- None")
    lines.append("\nAdvisory only. No task automation, delivery, upload, sync, or publishing was performed.")
    return "\n".join(lines) + "\n"


def render_decision_summary(record: dict[str, Any]) -> str:
    return "\n".join([
        f"# Decision Summary — {record.get('packet_id', 'unknown')}",
        "",
        f"Reviewer role: `{record.get('reviewer_role', 'unknown')}`",
        f"Decision: `{record.get('decision_state', 'unknown')}`",
        f"Decided at: `{record.get('decided_at', 'manual')}`",
        "",
        "## Rationale",
        record.get("rationale", ""),
        "",
        render_follow_up_actions(record).rstrip(),
        "",
        "## Guardrails",
        "- Local decision record only.",
        "- No automated approval, delivery, upload, sync, scheduler, credentials, platform edit, deletion, movement, or publishing.",
    ]) + "\n"
