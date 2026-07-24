from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from src.application.production_workflow_service import ProductionWorkflowError
from src.operator_api.studio_v2_runtime import StudioV2Service


def _schema_safe_content_state(self: StudioV2Service, content_id: UUID) -> dict[str, Any]:
    """Read one content workspace using only columns guaranteed by P84-P104 migrations."""
    detail = self.portfolio.detail(content_id)
    if not detail.get("ok"):
        raise HTTPException(status_code=404, detail="content_not_found")
    try:
        workflow = self.workflows.workflow_for_content(content_id=content_id)
    except ProductionWorkflowError as exc:
        if exc.code != "workflow_not_found":
            raise
        workflow = None

    with self.database.connection() as conn:
        script = conn.execute(
            """SELECT sd.*,sv.version AS current_version,sv.status AS current_version_status,
                      sv.created_by AS current_version_created_by,sv.created_at AS current_version_created_at
               FROM football_brief.script_documents sd
               JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
               WHERE sd.portfolio_content_id=%s""",
            (content_id,),
        ).fetchone()
        sections: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        if script is not None:
            sections = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_sections
                       WHERE script_version_id=%s ORDER BY sequence,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
            claims = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_claims
                       WHERE script_version_id=%s ORDER BY claim_key,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
            sources = [
                dict(row)
                for row in conn.execute(
                    """SELECT * FROM football_brief.script_sources
                       WHERE script_version_id=%s ORDER BY source_key,id""",
                    (script["current_version_id"],),
                ).fetchall()
            ]
        audio = conn.execute(
            """SELECT * FROM football_brief.audio_productions
               WHERE portfolio_content_id=%s ORDER BY created_at DESC LIMIT 1""",
            (content_id,),
        ).fetchone()
        visual = conn.execute(
            """SELECT * FROM football_brief.visual_projects
               WHERE portfolio_content_id=%s ORDER BY created_at DESC LIMIT 1""",
            (content_id,),
        ).fetchone()
        jobs = [
            dict(row)
            for row in conn.execute(
                """SELECT * FROM football_brief.generation_jobs
                   WHERE portfolio_content_id=%s ORDER BY queued_at DESC,id DESC LIMIT 100""",
                (content_id,),
            ).fetchall()
        ]
        visual_preset = conn.execute(
            """SELECT bvp.id
               FROM football_brief.portfolio_content pc
               LEFT JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
               LEFT JOIN football_brief.production_workflow_versions pwv ON pwv.id=pw.current_version_id
               LEFT JOIN football_brief.brand_visual_presets bvp
                 ON bvp.brand_profile_id=COALESCE(pc.brand_profile_id,NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid)
                AND bvp.preset_key='local-default' AND bvp.status='active'
               WHERE pc.id=%s""",
            (content_id,),
        ).fetchone()

    payload: dict[str, Any] = {
        "ok": True,
        "kind": "studio_v2_content_state",
        "item": detail["item"],
        "artifacts": detail.get("artifacts", []),
        "approvals": detail.get("approvals", []),
        "workflow": workflow,
        "script": dict(script) if script else None,
        "script_sections": sections,
        "script_claims": claims,
        "script_sources": sources,
        "audio": dict(audio) if audio else None,
        "visual": dict(visual) if visual else None,
        "jobs": jobs,
        "capabilities": {"visual_preset_ready": visual_preset is not None},
    }
    status, label, actions, blockers = self._next_actions(payload)
    payload.update(
        {
            "status": status,
            "status_label": label,
            "next_actions": actions,
            "blockers": blockers,
        }
    )
    return payload


def apply_studio_v2_schema_patch() -> None:
    """Install the schema-safe reader before Studio v2 routes instantiate their service."""
    StudioV2Service.content_state = _schema_safe_content_state  # type: ignore[method-assign]


__all__ = ["apply_studio_v2_schema_patch"]
