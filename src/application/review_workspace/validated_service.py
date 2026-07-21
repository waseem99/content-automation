from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.review_workspace.models import CompareTarget, ReviewTarget
from src.application.review_workspace.service import ReviewWorkspaceError, ReviewWorkspaceService


class ValidatedReviewWorkspaceService(ReviewWorkspaceService):
    """Public lineage helpers and response cleanup for the scoped operator API."""

    def compare(self, *, request: CompareTarget) -> dict[str, Any]:
        result = super().compare(request=request)
        result["current"].pop("_parent_id", None)
        if result["previous"] is not None:
            result["previous"].pop("_parent_id", None)
        return result

    def target_content_id(self, *, target_type: ReviewTarget, target_id: UUID) -> UUID:
        with self.database.connection() as conn:
            row = self._resolve_target(conn, target_type, target_id)
        return UUID(str(row["portfolio_content_id"]))

    def task_context(self, *, task_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT crt.*,mp.brand_id
                   FROM football_brief.creator_revision_tasks crt
                   JOIN football_brief.portfolio_content pc ON pc.id=crt.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE crt.id=%s""",
                (task_id,),
            ).fetchone()
        if not row:
            raise ReviewWorkspaceError("revision_task_not_found")
        return dict(row)

    def comment_context(self, *, comment_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT crc.*,mp.brand_id
                   FROM football_brief.creator_review_comments crc
                   JOIN football_brief.portfolio_content pc ON pc.id=crc.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE crc.id=%s""",
                (comment_id,),
            ).fetchone()
        if not row:
            raise ReviewWorkspaceError("review_comment_not_found")
        return dict(row)
