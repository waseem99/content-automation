"""Editorial status model and approval gate helpers for P29.

This module defines a review-only lifecycle for generated content from draft to
publish-export-ready output. It does not build UI, upload content, publish to
platforms, or bypass P26 risk blocks.
"""

from __future__ import annotations

from typing import Any

EDITORIAL_STATUS_SCHEMA_VERSION = "p29.editorial_status_model.v1"
EDITORIAL_STATUS_VALIDATION_SCHEMA_VERSION = "p29.editorial_status_validation.v1"

EDITORIAL_STATUSES = (
    "draft",
    "package_generated",
    "editorial_review",
    "rights_review",
    "revisions_required",
    "approved",
    "publish_export_ready",
    "published_external",
    "archived",
)

TERMINAL_STATUSES = (
    "published_external",
    "archived",
)

REQUIRED_GATE_FIELDS = (
    "editorial_gate_passed",
    "rights_gate_passed",
    "p26_publish_block_clear",
    "source_attribution_complete",
    "monetization_review_passed",
)

BLOCKER_TYPES = (
    "editorial_changes_required",
    "rights_review_required",
    "p26_publish_block",
    "missing_source_attribution",
    "monetization_review_required",
    "platform_export_not_ready",
)

ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("package_generated", "archived"),
    "package_generated": ("editorial_review", "rights_review", "revisions_required", "archived"),
    "editorial_review": ("rights_review", "revisions_required", "approved", "archived"),
    "rights_review": ("editorial_review", "revisions_required", "approved", "archived"),
    "revisions_required": ("draft", "package_generated", "editorial_review", "archived"),
    "approved": ("publish_export_ready", "revisions_required", "archived"),
    "publish_export_ready": ("published_external", "revisions_required", "archived"),
    "published_external": ("archived",),
    "archived": (),
}

STATUS_DESCRIPTIONS: dict[str, str] = {
    "draft": "Content is being drafted and has no package or approval status.",
    "package_generated": "A content package exists, but human editorial review has not passed.",
    "editorial_review": "Human review is checking script, claims, structure, safety, and editorial quality.",
    "rights_review": "Human review is checking source attribution, footage, music, visual asset, and usage rights.",
    "revisions_required": "The package is blocked until requested edits are completed and resubmitted.",
    "approved": "Editorial and rights gates are passed, but publish export still needs final readiness checks.",
    "publish_export_ready": "All required gates are passed and the package may move to manual export/publish operations.",
    "published_external": "A human has published externally and recorded the external status; no API upload is implied.",
    "archived": "The package is no longer active for production or publishing.",
}


def _status_entry(status: str) -> dict[str, Any]:
    can_move_to_publish_export = status == "publish_export_ready"
    return {
        "status": status,
        "description": STATUS_DESCRIPTIONS[status],
        "allowed_next_statuses": list(ALLOWED_TRANSITIONS[status]),
        "is_terminal": status in TERMINAL_STATUSES,
        "requires_human_review": status not in ("draft", "archived"),
        "can_move_to_publish_export": can_move_to_publish_export,
        "direct_platform_upload_allowed": False,
    }


def build_editorial_status_model() -> dict[str, Any]:
    """Build the deterministic P29 editorial status and gate model."""

    return {
        "schema_version": EDITORIAL_STATUS_SCHEMA_VERSION,
        "parent_epic": 331,
        "content_type": "editorial_status_model",
        "statuses": [_status_entry(status) for status in EDITORIAL_STATUSES],
        "allowed_transitions": {
            status: list(next_statuses) for status, next_statuses in ALLOWED_TRANSITIONS.items()
        },
        "approval_gates": {
            "required_for_approved": [
                "editorial_gate_passed",
                "rights_gate_passed",
                "p26_publish_block_clear",
                "source_attribution_complete",
            ],
            "required_for_publish_export_ready": list(REQUIRED_GATE_FIELDS),
            "rule": "No status implies publish-export readiness unless editorial, rights, source, monetization, and P26 publish-block gates are clear.",
        },
        "blocked_states": {
            "revisions_required": {
                "meaning": "Human reviewer requested changes before the item can continue.",
                "must_include_blocker_type": True,
                "allowed_blocker_types": list(BLOCKER_TYPES),
                "may_return_to": ["draft", "package_generated", "editorial_review"],
            },
            "p26_publish_block": {
                "meaning": "P26 risk rules block publish-export readiness.",
                "must_clear_before": ["approved", "publish_export_ready", "published_external"],
            },
        },
        "p26_alignment": {
            "p26_publish_block_clear_required": True,
            "blocked_content_cannot_be_approved": True,
            "blocked_content_cannot_be_publish_export_ready": True,
            "risk_review_must_remain_visible": True,
        },
        "review_record_required_fields": [
            "content_id",
            "current_status",
            "requested_status",
            "reviewer_id",
            "review_timestamp",
            "gate_results",
            "blockers",
            "transition_allowed",
        ],
        "out_of_scope": [
            "review UI",
            "platform upload",
            "automatic publishing",
            "platform credential storage",
        ],
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def required_gates_passed(gates: dict[str, bool]) -> bool:
    """Return true only when every required publish-export gate is true."""

    return all(gates.get(field) is True for field in REQUIRED_GATE_FIELDS)


def evaluate_status_transition(
    current_status: str,
    requested_status: str,
    gates: dict[str, bool] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate whether a status transition is allowed under P29 gates."""

    gate_values = gates or {}
    blocker_values = blockers or []
    errors: list[str] = []

    _require(current_status in EDITORIAL_STATUSES, errors, "current_status is not supported")
    _require(requested_status in EDITORIAL_STATUSES, errors, "requested_status is not supported")

    transition_allowed_by_graph = (
        requested_status in ALLOWED_TRANSITIONS.get(current_status, ())
        if current_status in EDITORIAL_STATUSES
        else False
    )
    if not transition_allowed_by_graph:
        errors.append("transition is not allowed by lifecycle graph")

    if requested_status in ("approved", "publish_export_ready", "published_external"):
        _require(gate_values.get("editorial_gate_passed") is True, errors, "editorial gate must pass")
        _require(gate_values.get("rights_gate_passed") is True, errors, "rights gate must pass")
        _require(gate_values.get("p26_publish_block_clear") is True, errors, "P26 publish block must be clear")
        _require(gate_values.get("source_attribution_complete") is True, errors, "source attribution must be complete")

    if requested_status in ("publish_export_ready", "published_external"):
        _require(gate_values.get("monetization_review_passed") is True, errors, "monetization review must pass")

    if blocker_values and requested_status in ("approved", "publish_export_ready", "published_external"):
        errors.append("blocked content cannot move to approval or publish-export states")

    return {
        "schema_version": "p29.editorial_transition_evaluation.v1",
        "current_status": current_status,
        "requested_status": requested_status,
        "transition_allowed": not errors,
        "transition_allowed_by_graph": transition_allowed_by_graph,
        "gates_checked": list(REQUIRED_GATE_FIELDS),
        "blockers": blocker_values,
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }


def validate_editorial_status_model(model: dict[str, Any]) -> dict[str, Any]:
    """Validate the P29 editorial status model contract."""

    errors: list[str] = []

    _require(model.get("schema_version") == EDITORIAL_STATUS_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(model.get("parent_epic") == 331, errors, "parent epic must be 331")
    _require(model.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(model.get("review_required") is True, errors, "review_required must remain true")

    statuses = model.get("statuses", [])
    _require(isinstance(statuses, list) and bool(statuses), errors, "statuses must be a non-empty list")
    status_names = [status.get("status") for status in statuses if isinstance(status, dict)]
    _require(tuple(status_names) == EDITORIAL_STATUSES, errors, "required editorial statuses missing or out of order")
    for status in statuses if isinstance(statuses, list) else []:
        _require(isinstance(status, dict), errors, "status entry must be an object")
        if not isinstance(status, dict):
            continue
        status_name = status.get("status")
        _require(status_name in EDITORIAL_STATUSES, errors, "unsupported status entry")
        _require(bool(status.get("description")), errors, "status description required")
        _require(isinstance(status.get("allowed_next_statuses"), list), errors, "allowed_next_statuses must be a list")
        _require(status.get("direct_platform_upload_allowed") is False, errors, "direct platform upload must remain false")
        if status_name == "publish_export_ready":
            _require(status.get("can_move_to_publish_export") is True, errors, "publish_export_ready must mark export readiness")
        else:
            _require(status.get("can_move_to_publish_export") is False, errors, f"{status_name} must not imply publish-export readiness")

    transitions = model.get("allowed_transitions", {})
    if not isinstance(transitions, dict):
        transitions = {}
    _require(set(EDITORIAL_STATUSES) <= set(transitions), errors, "allowed transitions missing statuses")
    for status, next_statuses in ALLOWED_TRANSITIONS.items():
        _require(tuple(transitions.get(status, [])) == next_statuses, errors, f"transition mismatch for {status}")

    approval_gates = model.get("approval_gates", {})
    if not isinstance(approval_gates, dict):
        approval_gates = {}
    _require(set(REQUIRED_GATE_FIELDS) <= set(approval_gates.get("required_for_publish_export_ready", [])), errors, "publish-export gates missing")
    _require("P26 publish-block gates are clear" in approval_gates.get("rule", ""), errors, "P26 gate rule required")

    blocked_states = model.get("blocked_states", {})
    if not isinstance(blocked_states, dict):
        blocked_states = {}
    _require("revisions_required" in blocked_states, errors, "revisions_required blocked state required")
    _require("p26_publish_block" in blocked_states, errors, "P26 publish block state required")
    revisions_required = blocked_states.get("revisions_required", {})
    if isinstance(revisions_required, dict):
        _require(set(BLOCKER_TYPES) <= set(revisions_required.get("allowed_blocker_types", [])), errors, "blocker types missing")

    p26_alignment = model.get("p26_alignment", {})
    if not isinstance(p26_alignment, dict):
        p26_alignment = {}
    _require(p26_alignment.get("p26_publish_block_clear_required") is True, errors, "P26 publish-block clear flag required")
    _require(p26_alignment.get("blocked_content_cannot_be_approved") is True, errors, "blocked content approval rule required")
    _require(p26_alignment.get("blocked_content_cannot_be_publish_export_ready") is True, errors, "blocked content export rule required")
    _require(p26_alignment.get("risk_review_must_remain_visible") is True, errors, "risk review visibility rule required")

    out_of_scope = model.get("out_of_scope", [])
    _require("review UI" in out_of_scope, errors, "review UI out-of-scope note required")
    _require("platform upload" in out_of_scope, errors, "platform upload out-of-scope note required")

    return {
        "schema_version": EDITORIAL_STATUS_VALIDATION_SCHEMA_VERSION,
        "is_valid": not errors,
        "statuses_checked": list(EDITORIAL_STATUSES),
        "gate_fields_checked": list(REQUIRED_GATE_FIELDS),
        "blocker_types_checked": list(BLOCKER_TYPES),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
