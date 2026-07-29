from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from src.application.scripts.automatic_evidence import AutomaticScriptEvidenceService
from src.application.scripts.models import ScriptDecision
from src.operator_api.access import OperatorIdentity
from src.operator_api.p110_runtime import P110Error, P110Service


_API_PATCHED = False
_WORKER_PATCHED = False


def install_p111_super_admin_override_patch() -> None:
    """Allow a Super Admin to approve unsupported factual claims in one audited action."""

    global _API_PATCHED
    if _API_PATCHED:
        return
    _API_PATCHED = True

    def decide_script(
        self: P110Service,
        *,
        document_id: UUID,
        request: Any,
        actor: OperatorIdentity,
    ) -> dict[str, Any]:
        try:
            with self.database.transaction() as conn:
                row = conn.execute(
                    """SELECT sd.id,sd.current_version_id,sd.lock_version,sv.status,sv.last_edited_by,
                              mp.brand_id,p.policy_key,p.rationale_required_for_override
                       FROM football_brief.script_documents sd
                       JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                       JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                       JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                       LEFT JOIN football_brief.brand_review_policies p
                         ON p.brand_id=mp.brand_id AND p.active=true
                       WHERE sd.id=%s FOR UPDATE OF sd,sv""",
                    (document_id,),
                ).fetchone()
                if row is None:
                    raise P110Error("script_document_not_found")
                if int(row["lock_version"]) != request.expected_lock_version:
                    raise P110Error(
                        "script_document_conflict",
                        details={"expected": request.expected_lock_version, "current": int(row["lock_version"])},
                    )
                if row["status"] != "in_review":
                    raise P110Error("script_version_not_in_review")

                policy = str(row["policy_key"] or "independent_review_required")
                same_actor = str(row["last_edited_by"]) == actor.operator_id
                self_review = bool(same_actor and actor.is_admin)
                if same_actor and not actor.is_admin:
                    raise P110Error("independent_script_review_required")
                if same_actor and policy == "independent_review_required":
                    raise P110Error("brand_policy_requires_independent_review")

                unsupported_rows = conn.execute(
                    """SELECT sc.id,sc.claim_key,sc.claim_text,sc.support_status,
                              NOT EXISTS (
                                  SELECT 1 FROM football_brief.script_claim_sources cs
                                  WHERE cs.claim_id=sc.id
                                    AND cs.script_version_id=sc.script_version_id
                                    AND cs.support_type IN ('direct','corroborating')
                              ) AS missing_support_link
                       FROM football_brief.script_claims sc
                       WHERE sc.script_version_id=%s
                         AND sc.claim_type='factual'
                         AND (
                             sc.support_status<>'supported'
                             OR NOT EXISTS (
                                 SELECT 1 FROM football_brief.script_claim_sources cs
                                 WHERE cs.claim_id=sc.id
                                   AND cs.script_version_id=sc.script_version_id
                                   AND cs.support_type IN ('direct','corroborating')
                             )
                         )
                       ORDER BY sc.created_at,sc.id""",
                    (row["current_version_id"],),
                ).fetchall()
                unsupported = [
                    {
                        "claim_id": str(item["id"]),
                        "claim_key": str(item["claim_key"]),
                        "claim_text": str(item["claim_text"]),
                        "support_status": str(item["support_status"]),
                        "missing_support_link": bool(item["missing_support_link"]),
                    }
                    for item in unsupported_rows
                ]
                override_unsupported = bool(
                    request.decision == ScriptDecision.APPROVED
                    and unsupported
                    and actor.is_super_admin
                )
                if request.decision == ScriptDecision.APPROVED and unsupported and not override_unsupported:
                    raise P110Error(
                        "unsupported_factual_claims",
                        details={
                            "message": "Approval is blocked until factual evidence is attached, or a Super Admin approves the exception.",
                            "count": len(unsupported),
                            "claims": unsupported,
                        },
                    )

                rationale = request.rationale.strip()
                if not rationale:
                    rationale = {
                        ScriptDecision.APPROVED: "Approved",
                        ScriptDecision.CHANGES_REQUESTED: "Changes requested",
                        ScriptDecision.REJECTED: "Rejected",
                    }[request.decision]
                if self_review and bool(row["rationale_required_for_override"]) and len(rationale) < 3:
                    raise P110Error("admin_override_rationale_required")

                override_reasons: list[str] = []
                if self_review:
                    override_reasons.append(f"Same-session Admin progression under {policy}")
                if override_unsupported:
                    override_reasons.append(
                        f"Super Admin accepted {len(unsupported)} unsupported or unlinked factual claim(s)"
                    )

                conn.execute(
                    """INSERT INTO football_brief.script_review_decisions
                       (script_document_id,script_version_id,decision,reviewer_operator_id,rationale,
                        document_lock_version,self_review,review_policy_key,override_reason,
                        unsupported_claim_override,unsupported_claim_count,unsupported_claim_snapshot)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        document_id,
                        row["current_version_id"],
                        request.decision.value,
                        actor.operator_id,
                        rationale,
                        request.expected_lock_version,
                        self_review,
                        policy,
                        "; ".join(override_reasons) or None,
                        override_unsupported,
                        len(unsupported) if override_unsupported else 0,
                        json.dumps(unsupported if override_unsupported else []),
                    ),
                )
                conn.execute(
                    "UPDATE football_brief.script_versions SET status=%s,decided_at=now() WHERE id=%s",
                    (request.decision.value, row["current_version_id"]),
                )
                updated = conn.execute(
                    """UPDATE football_brief.script_documents
                       SET lock_version=lock_version+1
                       WHERE id=%s AND lock_version=%s RETURNING id""",
                    (document_id, request.expected_lock_version),
                ).fetchone()
                if updated is None:
                    raise P110Error("script_document_conflict")
        except P110Error:
            raise
        except Exception as exc:
            message = str(exc)
            translations = {
                "Unsupported factual claims block script approval": (
                    "unsupported_factual_claims",
                    "Approval is blocked by unsupported factual claims.",
                ),
                "Unresolved script review actions block approval": (
                    "unresolved_script_review_actions",
                    "Resolve the outstanding script review actions before approval.",
                ),
                "Every approved script section requires a scene-plan entry": (
                    "missing_script_scene_plan",
                    "Every approved script section needs a scene-plan entry.",
                ),
                "Every final narration paragraph requires a claim mapping": (
                    "missing_script_claim_mapping",
                    "Every final narration paragraph needs a claim mapping.",
                ),
                "Script narration duration exceeds the approved tolerance": (
                    "script_duration_exceeds_tolerance",
                    "The script duration exceeds the configured tolerance.",
                ),
            }
            for text, (code, friendly) in translations.items():
                if text in message:
                    raise P110Error(code, details={"message": friendly}) from exc
            raise

        return {
            "ok": True,
            "kind": "p111_script_decision",
            "self_review": self_review,
            "review_policy_key": policy,
            "unsupported_claim_override": override_unsupported,
            "unsupported_claim_count": len(unsupported) if override_unsupported else 0,
            **self.scripts.detail(document_id=document_id),
        }

    P110Service.decide_script = decide_script  # type: ignore[method-assign]


def install_p111_worker_evidence_patch(worker_class: type[Any]) -> None:
    """Run best-effort factual evidence enrichment immediately after script generation."""

    global _WORKER_PATCHED
    if _WORKER_PATCHED:
        return
    _WORKER_PATCHED = True
    original = worker_class._script

    def _script(self: Any, job: dict[str, Any]) -> dict[str, Any]:
        output = original(self, job)
        document_id = UUID(str(output["script_document_id"]))
        try:
            summary = AutomaticScriptEvidenceService(self.database).enrich(
                document_id=document_id,
                actor=self.worker_id,
            )
        except Exception as exc:  # script generation succeeds even when the web provider is unavailable
            summary = {
                "attempted": 0,
                "auto_attached": 0,
                "unresolved": 0,
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }
        return {**output, "automatic_evidence": summary}

    worker_class._script = _script


__all__ = [
    "install_p111_super_admin_override_patch",
    "install_p111_worker_evidence_patch",
]
