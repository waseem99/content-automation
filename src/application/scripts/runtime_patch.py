from __future__ import annotations

from typing import Any

from src.application.scripts.models import ScriptDecision
from src.application.scripts.service import ScriptReviewError, ScriptReviewService
from src.application.scripts.validated_service import ValidatedScriptReviewService


_ORIGINAL_DECIDE = ScriptReviewService.decide
_DEFAULT_RATIONALES = {
    ScriptDecision.APPROVED: "Approved",
    ScriptDecision.CHANGES_REQUESTED: "Changes requested",
    ScriptDecision.REJECTED: "Rejected",
}
_DECISION_ERROR_MESSAGES = {
    "Unsupported factual claims block script approval": (
        "unsupported_factual_claims",
        "Approval is blocked because one or more factual claims still need a supporting source. Attach sources or request changes.",
    ),
    "Unresolved script review actions block approval": (
        "unresolved_script_review_actions",
        "Approval is blocked until the outstanding script review actions are resolved.",
    ),
    "Every approved script section requires a scene-plan entry": (
        "missing_script_scene_plan",
        "Approval is blocked because every script section needs a scene-plan entry.",
    ),
    "Every final narration paragraph requires a claim mapping": (
        "missing_script_claim_mapping",
        "Approval is blocked because every narration paragraph needs a claim mapping.",
    ),
    "Script narration duration exceeds the approved tolerance": (
        "script_duration_out_of_tolerance",
        "Approval is blocked because the estimated narration duration exceeds the allowed tolerance.",
    ),
    "Approved script word count must match its sections": (
        "script_word_count_mismatch",
        "Approval is blocked because the script word count does not match its sections.",
    ),
    "Approved script duration must match its sections": (
        "script_duration_mismatch",
        "Approval is blocked because the script duration does not match its sections.",
    ),
    "Independent script review is required": (
        "independent_script_review_required",
        "The person or worker that last edited this version cannot approve it. Use a different Reviewer, Admin, or Super Admin.",
    ),
}


def _normalize_rationale(decision: ScriptDecision, rationale: str | None) -> str:
    value = str(rationale or "").strip()
    if len(value) >= 3:
        return value
    if value:
        return f"{value}."
    return _DEFAULT_RATIONALES[decision]


def _decide_with_friendly_validation(
    self: ScriptReviewService,
    *,
    document_id,
    expected_lock_version: int,
    decision: ScriptDecision,
    rationale: str | None,
    reviewer: str,
) -> dict[str, Any]:
    normalized = _normalize_rationale(decision, rationale)
    try:
        return _ORIGINAL_DECIDE(
            self,
            document_id=document_id,
            expected_lock_version=expected_lock_version,
            decision=decision,
            rationale=normalized,
            reviewer=reviewer,
        )
    except ScriptReviewError:
        raise
    except Exception as exc:
        message = str(exc)
        for fragment, (code, friendly_message) in _DECISION_ERROR_MESSAGES.items():
            if fragment in message:
                raise ScriptReviewError(
                    "script_decision_blocked",
                    details={
                        "blockers": [
                            {
                                "code": code,
                                "message": friendly_message,
                            }
                        ]
                    },
                ) from exc
        raise


def install_validated_script_service() -> None:
    """Install validated revision copying and user-facing decision safeguards."""
    ScriptReviewService._copy_children = staticmethod(ValidatedScriptReviewService._copy_children)
    ScriptReviewService.decide = _decide_with_friendly_validation
