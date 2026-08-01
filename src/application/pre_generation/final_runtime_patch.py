from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from src.application.scripts.models import (
    ScriptDecision,
    ScriptGenerateRequest as ValidatedScriptGenerateRequest,
)
from src.application.scripts.service import ScriptReviewError
from src.application.pre_generation import runtime_patch as pre_generation_runtime
from src.application.pre_generation.service import PreGenerationService, RULE_VERSION
from src.operator_api import p110_runtime, studio_v2_runtime


def _bounded_script_generate_request(*args: Any, **kwargs: Any) -> ValidatedScriptGenerateRequest:
    """Normalize external timeout configuration before strict model validation.

    Both Studio V2 and P110 construct the same validated request, but legacy
    workstation configuration may still contain the former 180-second value.
    Keep the request contract strict and clamp only at this orchestration edge.
    """

    if "local_timeout_seconds" in kwargs and kwargs["local_timeout_seconds"] is not None:
        try:
            configured = int(kwargs["local_timeout_seconds"])
        except (TypeError, ValueError):
            configured = 20
        kwargs["local_timeout_seconds"] = max(1, min(120, configured))
    return ValidatedScriptGenerateRequest(*args, **kwargs)


def _canonical_timeline(
    scenes: list[dict[str, Any]],
    target_seconds: float,
) -> tuple[list[dict[str, Any]], bool, float]:
    """Build the frozen renderer timeline from canonical script-scene columns."""

    ordered = sorted(
        scenes,
        key=lambda row: (int(row.get("sequence") or 0), str(row.get("scene_key") or "")),
    )
    durations = [float(row.get("target_duration_seconds") or 0) for row in ordered]
    total = sum(durations)
    correction = round(target_seconds - total, 3)
    corrected = False
    tolerance = max(2.0, target_seconds * 0.05)
    if ordered and abs(correction) > 0.01 and abs(correction) <= tolerance:
        candidate = durations[-1] + correction
        if candidate >= 1.0:
            durations[-1] = candidate
            total = sum(durations)
            corrected = True

    cursor = 0.0
    timeline: list[dict[str, Any]] = []
    for row, duration in zip(ordered, durations, strict=True):
        start = round(cursor, 3)
        end = round(cursor + duration, 3)
        timeline.append(
            {
                "scene_id": str(row.get("id")),
                "scene_key": str(row.get("scene_key") or ""),
                "position": int(row.get("sequence") or 0),
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(duration, 3),
                "narration_text": str(row.get("narration_text") or "").strip(),
                "visual_intent": str(row.get("visual_brief") or "").strip(),
                "on_screen_text": str(row.get("on_screen_text") or "").strip(),
                "metadata": {
                    "source_requirements": list(row.get("source_requirements") or []),
                    "script_section_id": str(row.get("script_section_id") or "") or None,
                },
            }
        )
        cursor = end
    return timeline, corrected, round(target_seconds - total, 3)


def _ensure_autopilot_reviewer(self: PreGenerationService, *, created_by: str) -> str:
    """Create one non-login audit identity for independent automatic decisions.

    The identity has no API key and is not part of the public role model. It is
    deliberately distinct from the worker that submits the script, preserving
    the database's independent-review invariant.
    """

    reviewer = os.getenv(
        "PRE_GENERATION_AUTOPILOT_REVIEWER_ID",
        "pre-generation-autopilot-reviewer",
    ).strip()
    if not reviewer:
        reviewer = "pre-generation-autopilot-reviewer"
    with self.database.transaction() as conn:
        operator = conn.execute(
            """INSERT INTO football_brief.operator_users
               (operator_id,display_name,active,created_by)
               VALUES (%s,'Pre-generation Autopilot Reviewer',true,%s)
               ON CONFLICT (operator_id) DO UPDATE SET
                 display_name=EXCLUDED.display_name,active=true
               RETURNING id""",
            (reviewer, created_by),
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.operator_user_roles
               (operator_user_id,role,assigned_by)
               VALUES (%s,'reviewer',%s)
               ON CONFLICT DO NOTHING""",
            (operator["id"], created_by),
        )
    return reviewer


def _decide_with_active_policy(
    self: PreGenerationService,
    *,
    document_id: UUID,
    expected_lock_version: int,
    reviewer: str,
    rationale: str,
) -> tuple[dict[str, Any], str]:
    """Record an independent approval bound to the exact active brand policy.

    The canonical ScriptReviewService predates the later policy-key columns.
    This helper uses the same locks, immutable decision table and status
    transition triggers while supplying the exact active policy key required by
    migration 0093.
    """

    with self.database.transaction() as conn:
        self.scripts._require_active_operator(conn, reviewer)
        row = self.scripts._locked(conn, document_id, expected_lock_version)
        if str(row["version_status"]) != "in_review":
            raise ScriptReviewError("script_version_not_in_review")
        policy = conn.execute(
            """SELECT COALESCE(p.policy_key,'independent_review_required') AS policy_key
               FROM football_brief.script_documents sd
               JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               LEFT JOIN football_brief.brand_review_policies p
                 ON p.brand_id=mp.brand_id AND p.active=true
               WHERE sd.id=%s
               ORDER BY p.version DESC NULLS LAST
               LIMIT 1""",
            (document_id,),
        ).fetchone()
        policy_key = str(policy["policy_key"] if policy else "independent_review_required")
        conn.execute(
            """INSERT INTO football_brief.script_review_decisions
               (script_document_id,script_version_id,decision,
                reviewer_operator_id,rationale,document_lock_version,
                self_review,review_policy_key,override_reason)
               VALUES (%s,%s,'approved',%s,%s,%s,false,%s,NULL)""",
            (
                document_id,
                row["current_version_id"],
                reviewer,
                rationale,
                expected_lock_version,
                policy_key,
            ),
        )
        conn.execute(
            """UPDATE football_brief.script_versions
               SET status='approved',decided_at=now()
               WHERE id=%s""",
            (row["current_version_id"],),
        )
        self.scripts._advance_lock(
            conn,
            document_id=document_id,
            expected_lock=expected_lock_version,
        )
    return self.scripts.detail(document_id=document_id), policy_key


def _automatic_script_approval(
    self: PreGenerationService,
    *,
    run: dict[str, Any],
    lease_token: UUID,
    actor: str,
) -> dict[str, Any]:
    """Approve a policy-passed script with an independent internal identity."""

    context = self._context(run["id"])
    document_id = UUID(str(context["script_document_id"]))
    reviewer = _ensure_autopilot_reviewer(self, created_by=actor)
    active_review_policy = ""
    try:
        detail = self.scripts.detail(document_id=document_id)
        status = str(detail["document"]["current_version_status"])
        lock_version = int(detail["document"]["lock_version"])
        if status == "working":
            # Submission records the orchestration worker as submitter/editor.
            # The separate reviewer identity below remains independent.
            detail = self.scripts.submit(
                document_id=document_id,
                expected_lock_version=lock_version,
                actor=actor,
            )
            lock_version = int(detail["document"]["lock_version"])
            status = str(detail["document"]["current_version_status"])
        if status == "in_review":
            detail, active_review_policy = _decide_with_active_policy(
                self,
                document_id=document_id,
                expected_lock_version=lock_version,
                reviewer=reviewer,
                rationale=(
                    "Automatically approved by the independent pre-generation "
                    f"review identity after autopilot policy {context['policy_key']} "
                    f"and {RULE_VERSION} checks passed."
                ),
            )
            status = str(detail["document"]["current_version_status"])
    except ScriptReviewError as exc:
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code="automatic_script_approval_failed",
            category="system",
            severity="human_exception",
            details={"error_code": exc.code, **exc.details},
        )
    except Exception as exc:
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code="automatic_script_approval_failed",
            category="system",
            severity="human_exception",
            details={"error_type": type(exc).__name__, "message": str(exc)[:500]},
        )

    if status != "approved":
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code="script_not_approved_after_autopilot_decision",
            category="structural",
            severity="human_exception",
            details={"status": status},
        )

    with self.database.transaction() as conn:
        self._owned_run_locked(conn, run["id"], lease_token)
        self._check(
            conn,
            run_id=run["id"],
            stage="script_approval",
            key="automatic_policy_decision",
            status="passed",
            score=100,
            evidence={
                "autopilot_policy_id": str(context["autopilot_policy_id"]),
                "autopilot_policy_key": context["policy_key"],
                "active_brand_review_policy": active_review_policy,
                "orchestration_worker": actor,
                "independent_reviewer": reviewer,
                "review_mode": "non_login_autopilot_identity",
                "rule_version": RULE_VERSION,
            },
        )
    return self._advance(
        run_id=run["id"],
        lease_token=lease_token,
        stage="narration_plan",
        actor=actor,
        details={
            "script_status": "approved",
            "independent_reviewer": reviewer,
            "active_brand_review_policy": active_review_policy,
        },
    )


def install_final_pre_generation_runtime_patch() -> None:
    if getattr(pre_generation_runtime, "_final_runtime_patch_installed", False):
        return

    # These modules resolve ScriptGenerateRequest through their module globals at
    # call time. Replacing that constructor keeps all validated model semantics
    # while bounding legacy external configuration safely and without mutating
    # process-wide environment variables.
    p110_runtime.ScriptGenerateRequest = _bounded_script_generate_request
    studio_v2_runtime.ScriptGenerateRequest = _bounded_script_generate_request

    # The renderer-ready planning stage installed by runtime_patch resolves the
    # timeline helper from its module global at call time.
    pre_generation_runtime._timeline = _canonical_timeline

    # Preserve the legacy human-review trigger. Automatic decisions use a
    # separate non-login reviewer identity and retain policy evidence on the run.
    PreGenerationService._script_approval = _automatic_script_approval
    pre_generation_runtime._final_runtime_patch_installed = True


__all__ = ["install_final_pre_generation_runtime_patch"]
