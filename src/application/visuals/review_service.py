from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.application.visuals.models import (
    CandidateDecisionRequest,
    ProjectDecisionRequest,
    ShotDecisionRequest,
    SubmitProjectRequest,
)
from src.application.visuals.service import VisualProjectError
from src.application.visuals.validated_service import ValidatedVisualProjectService

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class VisualReviewService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.projects = ValidatedVisualProjectService(database)

    def decide_candidate(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        shot_version_id: UUID,
        candidate_id: UUID,
        request: CandidateDecisionRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            shot = self._locked_shot(
                conn,
                project_id=project_id,
                shot_id=shot_id,
                expected_lock=request.expected_shot_lock_version,
            )
            if shot["current_version_id"] != shot_version_id:
                raise VisualProjectError("stale_visual_shot_version")
            candidate = conn.execute(
                """SELECT * FROM football_brief.visual_candidates
                   WHERE id=%s AND visual_shot_version_id=%s""",
                (candidate_id, shot_version_id),
            ).fetchone()
            if not candidate:
                raise VisualProjectError("visual_candidate_not_found")
            conn.execute(
                """INSERT INTO football_brief.visual_candidate_decisions
                   (visual_project_id,visual_shot_id,visual_shot_version_id,
                    visual_candidate_id,decision,reviewer_operator_id,rationale,
                    shot_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    project_id,
                    shot_id,
                    shot_version_id,
                    candidate_id,
                    request.decision.value,
                    reviewer,
                    request.rationale,
                    request.expected_shot_lock_version,
                ),
            )
        return self.projects.detail(project_id=project_id)

    def decide_shot(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        shot_version_id: UUID,
        request: ShotDecisionRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            shot = self._locked_shot(
                conn,
                project_id=project_id,
                shot_id=shot_id,
                expected_lock=request.expected_shot_lock_version,
            )
            if shot["current_version_id"] != shot_version_id:
                raise VisualProjectError("stale_visual_shot_version")
            conn.execute(
                """INSERT INTO football_brief.visual_shot_decisions
                   (visual_project_id,visual_shot_id,visual_shot_version_id,
                    decision,reviewer_operator_id,rationale,shot_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    project_id,
                    shot_id,
                    shot_version_id,
                    request.decision.value,
                    reviewer,
                    request.rationale,
                    request.expected_shot_lock_version,
                ),
            )
        return self.projects.detail(project_id=project_id)

    def submit_project(
        self,
        *,
        project_id: UUID,
        request: SubmitProjectRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            project = self._locked_project(
                conn,
                project_id=project_id,
                expected_lock=request.expected_project_lock_version,
            )
            if project["status"] != "working":
                raise VisualProjectError("visual_project_not_working")
            updated = conn.execute(
                """UPDATE football_brief.visual_projects
                   SET status='ready_for_review',last_edited_by=%s,
                       lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s RETURNING id""",
                (actor, project_id, request.expected_project_lock_version),
            ).fetchone()
            if not updated:
                raise VisualProjectError("visual_project_conflict")
        return self.projects.detail(project_id=project_id)

    def decide_project(
        self,
        *,
        project_id: UUID,
        request: ProjectDecisionRequest,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            project = self._locked_project(
                conn,
                project_id=project_id,
                expected_lock=request.expected_project_lock_version,
            )
            if project["status"] != "ready_for_review":
                raise VisualProjectError("visual_project_not_ready_for_review")
            conn.execute(
                """INSERT INTO football_brief.visual_project_decisions
                   (visual_project_id,decision,reviewer_operator_id,rationale,
                    project_lock_version)
                   VALUES (%s,%s,%s,%s,%s)""",
                (
                    project_id,
                    request.decision.value,
                    reviewer,
                    request.rationale,
                    request.expected_project_lock_version,
                ),
            )
        return self.projects.detail(project_id=project_id)

    @staticmethod
    def _locked_shot(conn, *, project_id: UUID, shot_id: UUID, expected_lock: int):
        row = conn.execute(
            """SELECT * FROM football_brief.visual_shots
               WHERE id=%s AND visual_project_id=%s FOR UPDATE""",
            (shot_id, project_id),
        ).fetchone()
        if not row:
            raise VisualProjectError("visual_shot_not_found")
        if int(row["lock_version"]) != expected_lock:
            raise VisualProjectError(
                "visual_shot_conflict",
                details={"expected": expected_lock, "current": int(row["lock_version"])},
            )
        return row

    @staticmethod
    def _locked_project(conn, *, project_id: UUID, expected_lock: int):
        row = conn.execute(
            "SELECT * FROM football_brief.visual_projects WHERE id=%s FOR UPDATE",
            (project_id,),
        ).fetchone()
        if not row:
            raise VisualProjectError("visual_project_not_found")
        if int(row["lock_version"]) != expected_lock:
            raise VisualProjectError(
                "visual_project_conflict",
                details={"expected": expected_lock, "current": int(row["lock_version"])},
            )
        return row

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (operator_id,),
        ).fetchone()
        if not row or not row["active"]:
            raise VisualProjectError("operator_inactive_or_missing")
