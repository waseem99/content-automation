from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from src.application.visuals.models import ShotRevisionRequest
from src.application.visuals.service import VisualProjectError, VisualProjectService, _json


class ValidatedVisualProjectService(VisualProjectService):
    """P91 service with collision-free preset and prompt-revision lineage."""

    def _initial_context(self, *, content_id: UUID, visual_preset_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id AS portfolio_content_id,
                          pc.version AS content_version,
                          pc.brand_profile_id AS content_brand_profile_id,
                          sd.current_version_id AS script_version_id,
                          sv.status AS script_status,
                          bvp.id AS visual_preset_id,
                          bvp.brand_profile_id AS preset_brand_profile_id,
                          bvp.preset_key,
                          bvp.display_name AS preset_display_name,
                          bvp.version AS visual_preset_version,
                          bvp.status AS visual_preset_status,
                          bvp.palette,
                          bvp.subject_rules,
                          bvp.environment_rules,
                          bvp.camera_rules,
                          bvp.lighting_rules,
                          bvp.framing_rules,
                          bvp.negative_prompt,
                          bvp.exclusions
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.brand_visual_presets bvp ON bvp.id=%s
                   WHERE pc.id=%s""",
                (visual_preset_id, content_id),
            ).fetchone()
        if not row:
            raise VisualProjectError("approved_script_and_visual_preset_required")
        if row["script_status"] != "approved":
            raise VisualProjectError("approved_script_required")
        if (
            row["visual_preset_status"] != "active"
            or row["content_brand_profile_id"] != row["preset_brand_profile_id"]
        ):
            raise VisualProjectError("active_matching_visual_preset_required")
        context = dict(row)
        context["brand_profile_id"] = row["content_brand_profile_id"]
        context["status"] = row["visual_preset_status"]
        return context

    def revise_shot(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        request: ShotRevisionRequest,
        actor: str,
    ) -> dict[str, Any]:
        new_version_id = uuid4()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            shot = self._locked_shot(conn, project_id, shot_id, request.expected_shot_lock_version)
            if shot["status"] not in {"changes_requested", "rejected"}:
                raise VisualProjectError("visual_shot_not_revisable")

            version = conn.execute(
                """SELECT id,visual_shot_id,version,status,width,height,aspect_ratio,
                          candidate_target_count
                   FROM football_brief.visual_shot_versions
                   WHERE id=%s AND visual_shot_id=%s""",
                (shot["current_version_id"], shot_id),
            ).fetchone()
            scene = conn.execute(
                """SELECT sspe.*
                   FROM football_brief.visual_shots vs
                   JOIN football_brief.script_scene_plan_entries sspe
                     ON sspe.id=vs.scene_plan_entry_id
                   WHERE vs.id=%s AND vs.visual_project_id=%s""",
                (shot_id, project_id),
            ).fetchone()
            preset = conn.execute(
                """SELECT bvp.*
                   FROM football_brief.visual_projects vp
                   JOIN football_brief.brand_visual_presets bvp ON bvp.id=vp.visual_preset_id
                   WHERE vp.id=%s AND vp.status IN ('working','changes_requested')""",
                (project_id,),
            ).fetchone()
            if not version or not scene or not preset:
                raise VisualProjectError("visual_shot_revision_lineage_missing")
            references = conn.execute(
                """SELECT * FROM football_brief.visual_continuity_references
                   WHERE visual_project_id=%s AND active=true
                   ORDER BY reference_type,reference_key""",
                (project_id,),
            ).fetchall()
            compiled = self.compiler.compile(
                scene=dict(scene),
                preset=dict(preset),
                references=[dict(item) for item in references],
                prompt_patch=request.prompt_patch,
                negative_prompt_append=request.negative_prompt_append,
            )
            conn.execute(
                """INSERT INTO football_brief.visual_shot_versions
                   (id,visual_shot_id,version,parent_version_id,status,compiled_prompt,
                    negative_prompt,prompt_components,reference_snapshot,width,height,
                    aspect_ratio,candidate_target_count,revision_reason,created_by,last_edited_by)
                   VALUES (%s,%s,%s,%s,'working',%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_version_id,
                    shot_id,
                    int(version["version"]) + 1,
                    shot["current_version_id"],
                    compiled.prompt,
                    compiled.negative_prompt,
                    _json(compiled.components),
                    _json(compiled.reference_snapshot),
                    version["width"],
                    version["height"],
                    version["aspect_ratio"],
                    version["candidate_target_count"],
                    request.reason,
                    actor,
                    actor,
                ),
            )
            updated = conn.execute(
                """UPDATE football_brief.visual_shots
                   SET current_version_id=%s,selected_candidate_id=NULL,status='working',
                       lock_version=lock_version+1
                   WHERE id=%s AND visual_project_id=%s AND lock_version=%s
                   RETURNING id""",
                (
                    new_version_id,
                    shot_id,
                    project_id,
                    request.expected_shot_lock_version,
                ),
            ).fetchone()
            if not updated:
                raise VisualProjectError("visual_shot_conflict")
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_id,visual_shot_version_id,event,actor,details)
                   VALUES (%s,%s,%s,'shot_revised',%s,%s::jsonb)""",
                (
                    project_id,
                    shot_id,
                    new_version_id,
                    actor,
                    _json(
                        {
                            "parent_version_id": str(shot["current_version_id"]),
                            "reason": request.reason,
                            "prompt_patch": request.prompt_patch,
                        }
                    ),
                ),
            )
        self._ensure_shot_candidates(
            project_id=project_id,
            shot_id=shot_id,
            base_seed=request.base_seed,
            preferred_worker_id=request.preferred_worker_id,
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
            actor=actor,
        )
        return self.detail(project_id=project_id)
