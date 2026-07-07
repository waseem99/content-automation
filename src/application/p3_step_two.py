from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P3StepTwoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P3OptionReview:
    id: UUID
    workflow_run_id: UUID
    option_id: UUID
    requirement_id: UUID
    step_plan_id: UUID
    status: str
    reviewed_by: str | None
    rationale: str | None
    created_at: datetime
    reviewed_at: datetime | None


class P3StepTwoService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request_review(self, *, workflow_run_id: UUID, option_id: UUID, actor: str) -> P3OptionReview:
        with unit_of_work(self.database) as uow:
            option = _option_for_workflow(uow.conn, workflow_run_id, option_id)
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_option_reviews (
                    workflow_run_id, option_id, requirement_id, step_plan_id
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (workflow_run_id, option_id) DO UPDATE
                SET status = football_brief.p3_option_reviews.status
                RETURNING *
                """,
                (workflow_run_id, option_id, option["requirement_id"], option["step_plan_id"]),
            ).fetchone()
            review = P3OptionReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=None,
                event_type="p3_option_review_requested",
                actor=actor,
                reason="approval_required",
                payload={"option_id": str(option_id), "review_id": str(review.id)},
            )
            return review

    def decide(self, *, workflow_run_id: UUID, option_id: UUID, status: str, reviewed_by: str, rationale: str | None = None) -> P3OptionReview:
        if status not in {"approved", "returned"}:
            raise P3StepTwoError("status must be approved or returned")
        with unit_of_work(self.database) as uow:
            option = _option_for_workflow(uow.conn, workflow_run_id, option_id)
            existing = uow.conn.execute(
                "SELECT * FROM football_brief.p3_option_reviews WHERE workflow_run_id = %s AND option_id = %s",
                (workflow_run_id, option_id),
            ).fetchone()
            if existing is None:
                row = uow.conn.execute(
                    """
                    INSERT INTO football_brief.p3_option_reviews (
                        workflow_run_id, option_id, requirement_id, step_plan_id, status, reviewed_by, rationale, reviewed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    RETURNING *
                    """,
                    (workflow_run_id, option_id, option["requirement_id"], option["step_plan_id"], status, reviewed_by, rationale),
                ).fetchone()
            else:
                row = uow.conn.execute(
                    """
                    UPDATE football_brief.p3_option_reviews
                    SET status = %s, reviewed_by = %s, rationale = %s, reviewed_at = now()
                    WHERE workflow_run_id = %s AND option_id = %s
                    RETURNING *
                    """,
                    (status, reviewed_by, rationale, workflow_run_id, option_id),
                ).fetchone()
            uow.conn.execute(
                "UPDATE football_brief.p3_options SET status = %s WHERE id = %s",
                ("chosen" if status == "approved" else "returned", option_id),
            )
            review = P3OptionReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=None,
                event_type="p3_option_review_decided",
                actor=reviewed_by,
                reason=status,
                payload={"option_id": str(option_id), "review_id": str(review.id), "status": status},
            )
            return review

    def require_approved(self, *, workflow_run_id: UUID, option_id: UUID) -> dict[str, Any]:
        with unit_of_work(self.database) as uow:
            option = _option_for_workflow(uow.conn, workflow_run_id, option_id)
            review = uow.conn.execute(
                "SELECT * FROM football_brief.p3_option_reviews WHERE workflow_run_id = %s AND option_id = %s",
                (workflow_run_id, option_id),
            ).fetchone()
            if review is None:
                raise P3StepTwoError("option approval is missing")
            if review["status"] != "approved":
                raise P3StepTwoError("option is not approved")
            return dict(option)

    def pending(self, workflow_run_id: UUID) -> list[P3OptionReview]:
        with unit_of_work(self.database) as uow:
            rows = uow.conn.execute(
                """
                SELECT * FROM football_brief.p3_option_reviews
                WHERE workflow_run_id = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            return [P3OptionReview(**row) for row in rows]


def _option_for_workflow(conn, workflow_run_id: UUID, option_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM football_brief.p3_options WHERE workflow_run_id = %s AND id = %s",
        (workflow_run_id, option_id),
    ).fetchone()
    if row is None:
        raise P3StepTwoError("option was not found for workflow")
    return dict(row)
