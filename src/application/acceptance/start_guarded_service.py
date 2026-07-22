from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.acceptance.service import AcceptancePilotError
from src.application.acceptance.validated_service import ValidatedAcceptancePilotService


class StartGuardedAcceptancePilotService(ValidatedAcceptancePilotService):
    """Canonical acceptance service with durable start actor enforcement."""

    def start(self, *, pilot_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            current = conn.execute(
                """SELECT id,status,acceptance_policy
                   FROM football_brief.acceptance_pilots
                   WHERE id=%s FOR UPDATE""",
                (pilot_id,),
            ).fetchone()
            if not current:
                raise AcceptancePilotError("pilot_not_found")
            policy = current["acceptance_policy"] or {}
            if policy.get("bootstrap_kind") == "controlled_draft":
                raise AcceptancePilotError(
                    "pilot_controlled_start_required",
                    details={
                        "pilot_id": str(pilot_id),
                        "required_endpoint": (
                            f"/acceptance/pilots/{pilot_id}/start-controlled"
                        ),
                    },
                )
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='running',started_by=%s,started_at=now()
                   WHERE id=%s AND status='draft' RETURNING *""",
                (actor, pilot_id),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_startable")
            self._event(
                conn,
                pilot_id,
                None,
                "pilot_started",
                actor,
                {"start_mode": "legacy"},
            )
        return {"ok": True, "pilot": dict(pilot)}


__all__ = ["StartGuardedAcceptancePilotService"]
