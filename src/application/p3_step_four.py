from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P3StepFourError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P3PackageReview:
    id: UUID
    workflow_run_id: UUID
    package_id: UUID
    step_plan_id: UUID
    status: str
    reviewed_by: str | None
    rationale: str | None
    decision_metadata: dict[str, Any]
    created_at: datetime
    reviewed_at: datetime | None


class P3PackageReviewService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request_review(self, *, workflow_run_id: UUID, package_id: UUID, actor: str) -> P3PackageReview:
        with unit_of_work(self.database) as uow:
            package = _package_for_workflow(uow.conn, workflow_run_id, package_id)
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_package_reviews (workflow_run_id, package_id, step_plan_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (workflow_run_id, package_id) DO UPDATE
                SET status = football_brief.p3_package_reviews.status
                RETURNING *
                """,
                (workflow_run_id, package_id, package["step_plan_id"]),
            ).fetchone()
            review = P3PackageReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=package["stage_execution_id"],
                event_type="p3_package_review_requested",
                actor=actor,
                reason="final_gate_required",
                payload={"package_id": str(package_id), "review_id": str(review.id)},
            )
            return review

    def decide(self, *, workflow_run_id: UUID, package_id: UUID, status: str, reviewed_by: str, rationale: str | None = None, decision_metadata: dict[str, Any] | None = None) -> P3PackageReview:
        if status not in {"approved", "returned"}:
            raise P3StepFourError("status must be approved or returned")
        metadata = dict(decision_metadata or {})
        with unit_of_work(self.database) as uow:
            package = _package_for_workflow(uow.conn, workflow_run_id, package_id)
            existing = uow.conn.execute(
                "SELECT * FROM football_brief.p3_package_reviews WHERE workflow_run_id = %s AND package_id = %s",
                (workflow_run_id, package_id),
            ).fetchone()
            if existing is None:
                row = uow.conn.execute(
                    """
                    INSERT INTO football_brief.p3_package_reviews (
                        workflow_run_id, package_id, step_plan_id, status,
                        reviewed_by, rationale, decision_metadata, reviewed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    RETURNING *
                    """,
                    (workflow_run_id, package_id, package["step_plan_id"], status, reviewed_by, rationale, Jsonb(metadata)),
                ).fetchone()
            else:
                row = uow.conn.execute(
                    """
                    UPDATE football_brief.p3_package_reviews
                    SET status = %s,
                        reviewed_by = %s,
                        rationale = %s,
                        decision_metadata = %s,
                        reviewed_at = now()
                    WHERE workflow_run_id = %s AND package_id = %s
                    RETURNING *
                    """,
                    (status, reviewed_by, rationale, Jsonb(metadata), workflow_run_id, package_id),
                ).fetchone()
            review = P3PackageReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=package["stage_execution_id"],
                event_type="p3_package_review_decided",
                actor=reviewed_by,
                reason=status,
                payload={"package_id": str(package_id), "review_id": str(review.id), "status": status},
            )
            return review

    def require_approved(self, *, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
        with unit_of_work(self.database) as uow:
            package = _package_for_workflow(uow.conn, workflow_run_id, package_id)
            review = uow.conn.execute(
                "SELECT * FROM football_brief.p3_package_reviews WHERE workflow_run_id = %s AND package_id = %s",
                (workflow_run_id, package_id),
            ).fetchone()
            if review is None:
                raise P3StepFourError("package approval is missing")
            if review["status"] != "approved":
                raise P3StepFourError("package is not approved")
            return dict(package)

    def pending(self, workflow_run_id: UUID) -> list[P3PackageReview]:
        with unit_of_work(self.database) as uow:
            rows = uow.conn.execute(
                """
                SELECT * FROM football_brief.p3_package_reviews
                WHERE workflow_run_id = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            return [P3PackageReview(**row) for row in rows]


def _package_for_workflow(conn, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM football_brief.p3_packages WHERE workflow_run_id = %s AND id = %s",
        (workflow_run_id, package_id),
    ).fetchone()
    if row is None:
        raise P3StepFourError("package was not found for workflow")
    return dict(row)
