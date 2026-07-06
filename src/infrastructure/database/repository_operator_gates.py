from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.human_review_models import HumanReview, ReviewDecisionCreate, ReviewHistory, ReviewRequest, ReviewRequestCreate
from src.infrastructure.database.repository_base import BaseRepository


class OperatorGateRequestRepository(BaseRepository[ReviewRequest]):
    def create(self, data: ReviewRequestCreate) -> ReviewRequest:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.human_review_requests (
                workflow_run_id, stage_execution_id, target_type, target_id,
                review_type, assigned_to, requested_by, reason,
                prevent_self_approval, required_checklist, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.stage_execution_id,
                data.target_type.value,
                data.target_id,
                data.review_type,
                data.assigned_to,
                data.requested_by,
                data.reason,
                data.prevent_self_approval,
                Jsonb(data.required_checklist),
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, ReviewRequest, "operator gate request")

    def get(self, request_id: UUID) -> ReviewRequest:
        row = self.conn.execute("SELECT * FROM football_brief.human_review_requests WHERE id = %s", (request_id,)).fetchone()
        return self.required(row, ReviewRequest, "operator gate request")


class OperatorGateDecisionRepository(BaseRepository[HumanReview]):
    def create(self, data: ReviewDecisionCreate) -> HumanReview:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.human_reviews (
                workflow_run_id, stage_execution_id, review_request_id,
                review_type, decision, reviewer, rationale, checklist,
                target_type, target_id, supersedes_review_id,
                disclosure_texts, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.stage_execution_id,
                data.review_request_id,
                data.review_type,
                data.decision.value,
                data.reviewer,
                data.rationale,
                Jsonb(data.checklist),
                data.target_type.value if data.target_type else None,
                data.target_id,
                data.supersedes_review_id,
                Jsonb(data.disclosure_texts),
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, HumanReview, "operator gate decision")

    def history_for_workflow(self, workflow_run_id: UUID) -> ReviewHistory:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.human_reviews WHERE workflow_run_id = %s ORDER BY created_at ASC",
            (workflow_run_id,),
        ).fetchall()
        return ReviewHistory(workflow_run_id=workflow_run_id, decisions=tuple(HumanReview.model_validate(row) for row in rows))

    def history_for_stage(self, stage_execution_id: UUID) -> tuple[HumanReview, ...]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.human_reviews WHERE stage_execution_id = %s ORDER BY created_at ASC",
            (stage_execution_id,),
        ).fetchall()
        return tuple(HumanReview.model_validate(row) for row in rows)
