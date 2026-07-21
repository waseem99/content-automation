from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.review_workspace.models import CompareTarget, ReviewTarget
from src.application.review_workspace.service import ReviewWorkspaceError, ReviewWorkspaceService


class ValidatedReviewWorkspaceService(ReviewWorkspaceService):
    """Public lineage helpers and response cleanup for the scoped operator API."""

    def workspace(self, *, content_id: UUID) -> dict[str, Any]:
        result = super().workspace(content_id=content_id)
        with self.database.connection() as conn:
            workflow_decisions = conn.execute(
                """SELECT pwd.*,ou.display_name AS reviewer_name
                   FROM football_brief.production_workflow_decisions pwd
                   JOIN football_brief.production_workflows pw ON pw.id=pwd.workflow_id
                   JOIN football_brief.operator_users ou ON ou.operator_id=pwd.reviewer_operator_id
                   WHERE pw.portfolio_content_id=%s
                   ORDER BY pwd.created_at,pwd.id""",
                (content_id,),
            ).fetchall()
            script_decisions = conn.execute(
                """SELECT srd.*,ou.display_name AS reviewer_name
                   FROM football_brief.script_review_decisions srd
                   JOIN football_brief.script_documents sd ON sd.id=srd.script_document_id
                   JOIN football_brief.operator_users ou ON ou.operator_id=srd.reviewer_operator_id
                   WHERE sd.portfolio_content_id=%s
                   ORDER BY srd.created_at,srd.id""",
                (content_id,),
            ).fetchall()
            audio_decisions = conn.execute(
                """SELECT ard.*,ou.display_name AS reviewer_name
                   FROM football_brief.audio_review_decisions ard
                   JOIN football_brief.audio_productions ap ON ap.id=ard.audio_production_id
                   JOIN football_brief.operator_users ou ON ou.operator_id=ard.reviewer_operator_id
                   WHERE ap.portfolio_content_id=%s
                   ORDER BY ard.created_at,ard.id""",
                (content_id,),
            ).fetchall()
            visual_project_decisions = conn.execute(
                """SELECT vpd.*,ou.display_name AS reviewer_name
                   FROM football_brief.visual_project_decisions vpd
                   JOIN football_brief.visual_projects vp ON vp.id=vpd.visual_project_id
                   JOIN football_brief.operator_users ou ON ou.operator_id=vpd.reviewer_operator_id
                   WHERE vp.portfolio_content_id=%s
                   ORDER BY vpd.created_at,vpd.id""",
                (content_id,),
            ).fetchall()
            visual_candidate_decisions = conn.execute(
                """SELECT vcd.*,ou.display_name AS reviewer_name
                   FROM football_brief.visual_candidate_decisions vcd
                   JOIN football_brief.visual_projects vp ON vp.id=vcd.visual_project_id
                   JOIN football_brief.operator_users ou ON ou.operator_id=vcd.reviewer_operator_id
                   WHERE vp.portfolio_content_id=%s
                   ORDER BY vcd.created_at,vcd.id""",
                (content_id,),
            ).fetchall()
            render_jobs = conn.execute(
                """SELECT id,job_type,status,provider,model_id,input_payload,output_payload,
                          error_code,error_message,queued_at,started_at,finished_at
                   FROM football_brief.generation_jobs
                   WHERE portfolio_content_id=%s
                     AND job_type IN ('preview','assembly','caption','thumbnail','package')
                   ORDER BY queued_at DESC,id DESC""",
                (content_id,),
            ).fetchall()
        result["decision_history"] = {
            "workflow": [dict(row) for row in workflow_decisions],
            "script": [dict(row) for row in script_decisions],
            "audio": [dict(row) for row in audio_decisions],
            "visual_project": [dict(row) for row in visual_project_decisions],
            "visual_candidate": [dict(row) for row in visual_candidate_decisions],
        }
        result["render_jobs"] = [dict(row) for row in render_jobs]
        return result

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
