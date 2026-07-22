from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.acceptance.models import EvidenceCategory, PilotRetireRequest
from src.application.acceptance.service import AcceptancePilotError, AcceptancePilotService, _digest


class ValidatedAcceptancePilotService(AcceptancePilotService):
    """Acceptance collector with exact canonical subjects and immutable revision recovery."""

    def retire(
        self,
        *,
        pilot_id: UUID,
        request: PilotRetireRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s AND status IN ('running','blocked') RETURNING *""",
                (actor, pilot_id),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_retirable")
            self._event(
                conn,
                pilot_id,
                None,
                "pilot_retired",
                actor,
                {"reason": request.reason},
            )
        return {"ok": True, "pilot": dict(pilot)}

    def _system_checks(self, conn: Any, context: Any) -> dict[EvidenceCategory, dict[str, Any]]:
        checks = super()._system_checks(conn, context)
        if checks[EvidenceCategory.SOURCE_EVIDENCE]["passed"]:
            checks[EvidenceCategory.SOURCE_EVIDENCE]["subject_id"] = checks[
                EvidenceCategory.SCRIPT_APPROVAL
            ]["subject_id"]
            checks[EvidenceCategory.SOURCE_EVIDENCE]["subject_version"] = checks[
                EvidenceCategory.SCRIPT_APPROVAL
            ]["subject_version"]
        if (
            checks[EvidenceCategory.RENDERER_LINEAGE]["passed"]
            and str(checks[EvidenceCategory.RENDERER_LINEAGE]["subject_id"]).startswith("aggregate:")
        ):
            checks[EvidenceCategory.RENDERER_LINEAGE]["subject_id"] = checks[
                EvidenceCategory.ROUTING_EXPLANATION
            ]["subject_id"]
            checks[EvidenceCategory.RENDERER_LINEAGE]["subject_version"] = checks[
                EvidenceCategory.ROUTING_EXPLANATION
            ]["subject_version"]
        return checks

    @staticmethod
    def _result(value: Any, subject_type: str, details: Any) -> dict[str, Any]:
        result = AcceptancePilotService._result(value, subject_type, details)
        normalized = result["details"]
        exact_fields = {
            "audio_mix_version": "mix_id",
            "production_spend_decision": "spend_decision_id",
            "shared_artifact_version": "output_artifact_version_id",
            "platform_delivery_request": "delivery_request_id",
        }
        exact_field = exact_fields.get(subject_type)
        if result["passed"] and exact_field and normalized.get(exact_field):
            result["subject_id"] = str(normalized[exact_field])
        if result["passed"] and str(result["subject_id"]).startswith("missing:"):
            result["subject_id"] = f"aggregate:{_digest(normalized)}"
        return result
