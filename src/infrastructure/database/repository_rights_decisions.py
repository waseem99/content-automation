from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from src.application.rights.decision_models import AssetRightsDecision
from src.application.rights.request_models import RightsGateRequest


class RightsGateEvaluationRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(
        self,
        *,
        request: RightsGateRequest,
        policy_version: str,
        policy_hash: str,
        evaluation_fingerprint: str,
        outcome: str,
        reason_codes: tuple[str, ...],
        obligations: dict,
        evaluated_at: datetime,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.rights_gate_evaluations (
                workflow_run_id,
                stage_execution_id,
                gate_point,
                platform,
                territory,
                campaign,
                requested_uses,
                policy_version,
                policy_hash,
                evaluation_fingerprint,
                outcome,
                reason_codes,
                obligations,
                evaluated_by,
                evaluated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            ) RETURNING *
            """,
            (
                request.workflow_run_id,
                request.stage_execution_id,
                request.gate_point.value,
                request.platform.value,
                request.territory,
                request.campaign,
                list(request.requested_uses()),
                policy_version,
                policy_hash,
                evaluation_fingerprint,
                outcome,
                list(reason_codes),
                Jsonb(obligations),
                request.evaluated_by,
                evaluated_at,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("Rights gate evaluation was not persisted")
        return row

    def add_asset_decision(
        self,
        *,
        evaluation_id: UUID,
        decision: AssetRightsDecision,
        evaluated_at: datetime,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.rights_gate_asset_decisions (
                evaluation_id,
                asset_id,
                asset_sha256,
                selected_asset_rights_id,
                outcome,
                reason_codes,
                evidence_ids,
                obligations,
                evaluated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                evaluation_id,
                decision.asset_id,
                decision.asset_sha256,
                decision.selected_rights_id,
                decision.outcome.value,
                [code.value for code in decision.reason_codes],
                list(decision.evidence_ids),
                Jsonb(decision.obligations.model_dump(mode="json")),
                evaluated_at,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("Rights gate asset decision was not persisted")
        return row

    def get(self, evaluation_id: UUID) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM football_brief.rights_gate_evaluations WHERE id = %s",
            (evaluation_id,),
        ).fetchone()

    def list_asset_decisions(self, evaluation_id: UUID) -> list[dict]:
        return self.conn.execute(
            """
            SELECT *
            FROM football_brief.rights_gate_asset_decisions
            WHERE evaluation_id = %s
            ORDER BY asset_id
            """,
            (evaluation_id,),
        ).fetchall()
