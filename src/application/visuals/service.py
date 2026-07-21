from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from src.application.generation_jobs.service import GenerationJobService
from src.application.visuals.adapters import (
    LocalKeyframeJobAdapter,
    LocalVisualCandidateContext,
    VisualPromptCompiler,
    candidate_seed,
)
from src.application.visuals.models import (
    CandidateResult,
    ReviewActionRequest,
    ShotRevisionRequest,
    VisualProjectInitializeRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class VisualProjectError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class VisualProjectService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.jobs = GenerationJobService(database)
        self.compiler = VisualPromptCompiler()
        self.keyframes = LocalKeyframeJobAdapter()

    def initialize(
        self,
        *,
        content_id: UUID,
        request: VisualProjectInitializeRequest,
        actor: str,
    ) -> dict[str, Any]:
        context = self._initial_context(content_id=content_id, visual_preset_id=request.visual_preset_id)
        existing_project_id: UUID | None = None
        created = False
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            existing = conn.execute(
                """SELECT * FROM football_brief.visual_projects
                   WHERE portfolio_content_id=%s AND script_version_id=%s
                   FOR UPDATE""",
                (content_id, context["script_version_id"]),
            ).fetchone()
            if existing:
                existing_project_id = existing["id"]
            else:
                live = conn.execute(
                    """SELECT * FROM football_brief.visual_projects
                       WHERE portfolio_content_id=%s
                         AND status IN ('working','ready_for_review','approved')
                       FOR UPDATE""",
                    (content_id,),
                ).fetchone()
                if live:
                    if live["status"] != "approved":
                        raise VisualProjectError(
                            "visual_project_already_active",
                            details={"project_id": str(live["id"]), "status": live["status"]},
                        )
                    conn.execute(
                        """UPDATE football_brief.visual_projects
                           SET status='superseded',last_edited_by=%s,lock_version=lock_version+1
                           WHERE id=%s""",
                        (actor, live["id"]),
                    )
                    conn.execute(
                        """INSERT INTO football_brief.visual_project_events
                           (visual_project_id,event,actor,details)
                           VALUES (%s,'superseded',%s,%s::jsonb)""",
                        (
                            live["id"],
                            actor,
                            _json({"replacement_script_version_id": str(context["script_version_id"])}),
                        ),
                    )
                project = conn.execute(
                    """INSERT INTO football_brief.visual_projects
                       (portfolio_content_id,content_version,script_version_id,brand_profile_id,
                        visual_preset_id,status,provider,model_id,candidate_count,
                        external_fee_incurred,actual_cost_usd,lock_version,created_by,last_edited_by)
                       VALUES (%s,%s,%s,%s,%s,'working',%s,%s,%s,false,0,1,%s,%s)
                       RETURNING *""",
                    (
                        content_id,
                        context["content_version"],
                        context["script_version_id"],
                        context["brand_profile_id"],
                        request.visual_preset_id,
                        request.provider,
                        request.model_id,
                        request.candidate_count,
                        actor,
                        actor,
                    ),
                ).fetchone()
                existing_project_id = project["id"]
                references: list[dict[str, Any]] = []
                for item in request.continuity_references:
                    row = conn.execute(
                        """INSERT INTO football_brief.visual_continuity_references
                           (visual_project_id,reference_key,reference_type,asset_id,
                            reference_fingerprint,description,attributes,created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                        (
                            project["id"],
                            item.reference_key,
                            item.reference_type,
                            item.asset_id,
                            item.reference_fingerprint,
                            item.description,
                            _json(item.attributes),
                            actor,
                        ),
                    ).fetchone()
                    references.append(dict(row))
                scenes = conn.execute(
                    """SELECT * FROM football_brief.script_scene_plan_entries
                       WHERE script_version_id=%s ORDER BY sequence""",
                    (context["script_version_id"],),
                ).fetchall()
                if not scenes:
                    raise VisualProjectError("approved_script_has_no_scene_plan")
                preset = dict(context)
                for scene in scenes:
                    compiled = self.compiler.compile(
                        scene=dict(scene),
                        preset=preset,
                        references=references,
                    )
                    shot_id = uuid4()
                    version_id = uuid4()
                    conn.execute(
                        """INSERT INTO football_brief.visual_shots
                           (id,visual_project_id,scene_plan_entry_id,sequence,current_version_id,
                            status,lock_version,created_by)
                           VALUES (%s,%s,%s,%s,%s,'working',1,%s)""",
                        (
                            shot_id,
                            project["id"],
                            scene["id"],
                            scene["sequence"],
                            version_id,
                            actor,
                        ),
                    )
                    conn.execute(
                        """INSERT INTO football_brief.visual_shot_versions
                           (id,visual_shot_id,version,status,compiled_prompt,negative_prompt,
                            prompt_components,reference_snapshot,width,height,aspect_ratio,
                            candidate_target_count,created_by,last_edited_by)
                           VALUES (%s,%s,1,'working',%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)""",
                        (
                            version_id,
                            shot_id,
                            compiled.prompt,
                            compiled.negative_prompt,
                            _json(compiled.components),
                            _json(compiled.reference_snapshot),
                            request.width,
                            request.height,
                            f"{request.width}:{request.height}",
                            request.candidate_count,
                            actor,
                            actor,
                        ),
                    )
                conn.execute(
                    """INSERT INTO football_brief.visual_project_events
                       (visual_project_id,event,actor,details)
                       VALUES (%s,'initialized',%s,%s::jsonb)""",
                    (
                        project["id"],
                        actor,
                        _json(
                            {
                                "script_version_id": str(context["script_version_id"]),
                                "visual_preset_id": str(request.visual_preset_id),
                                "provider": request.provider,
                                "model_id": request.model_id,
                                "candidate_count": request.candidate_count,
                                "external_fee_incurred": False,
                            }
                        ),
                    ),
                )
                created = True
        assert existing_project_id is not None
        self._ensure_project_candidates(
            project_id=existing_project_id,
            base_seed=request.base_seed,
            preferred_worker_id=request.preferred_worker_id,
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
            actor=actor,
        )
        result = self.detail(project_id=existing_project_id)
        result["created"] = created
        return result

    def detail(self, *, project_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            project = conn.execute(
                """SELECT vp.*,pc.title,pc.concept,pc.format AS content_format,
                          mp.brand_id,b.slug AS brand_slug,b.display_name AS brand_name,
                          sv.version AS script_version,bvp.preset_key,bvp.display_name AS preset_name,
                          pw.id AS workflow_id,pw.current_version_id AS workflow_version_id
                   FROM football_brief.visual_projects vp
                   JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   JOIN football_brief.script_versions sv ON sv.id=vp.script_version_id
                   JOIN football_brief.brand_visual_presets bvp ON bvp.id=vp.visual_preset_id
                   LEFT JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   WHERE vp.id=%s""",
                (project_id,),
            ).fetchone()
            if not project:
                raise VisualProjectError("visual_project_not_found")
            references = conn.execute(
                """SELECT * FROM football_brief.visual_continuity_references
                   WHERE visual_project_id=%s ORDER BY reference_type,reference_key""",
                (project_id,),
            ).fetchall()
            shots = conn.execute(
                """SELECT vs.*,vsv.version AS current_version,vsv.status AS current_version_status,
                          vsv.compiled_prompt,vsv.negative_prompt,vsv.width,vsv.height,vsv.aspect_ratio,
                          sspe.scene_key,sspe.visual_brief,sspe.narration_text
                   FROM football_brief.visual_shots vs
                   JOIN football_brief.visual_shot_versions vsv ON vsv.id=vs.current_version_id
                   JOIN football_brief.script_scene_plan_entries sspe ON sspe.id=vs.scene_plan_entry_id
                   WHERE vs.visual_project_id=%s ORDER BY vs.sequence""",
                (project_id,),
            ).fetchall()
            versions = conn.execute(
                """SELECT vsv.* FROM football_brief.visual_shot_versions vsv
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   WHERE vs.visual_project_id=%s ORDER BY vs.sequence,vsv.version DESC""",
                (project_id,),
            ).fetchall()
            candidates = conn.execute(
                """SELECT vc.*,gj.status AS generation_job_status
                   FROM football_brief.visual_candidates vc
                   JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=vc.generation_job_id
                   WHERE vs.visual_project_id=%s
                   ORDER BY vs.sequence,vsv.version,vc.ordinal""",
                (project_id,),
            ).fetchall()
            checks = conn.execute(
                """SELECT vcc.* FROM football_brief.visual_candidate_checks vcc
                   JOIN football_brief.visual_candidates vc ON vc.id=vcc.visual_candidate_id
                   JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   WHERE vs.visual_project_id=%s ORDER BY vcc.visual_candidate_id,vcc.check_type""",
                (project_id,),
            ).fetchall()
            actions = conn.execute(
                """SELECT vsra.*,u.display_name AS author_name
                   FROM football_brief.visual_shot_review_actions vsra
                   JOIN football_brief.operator_users u ON u.operator_id=vsra.author_operator_id
                   WHERE vsra.visual_project_id=%s ORDER BY vsra.created_at,vsra.id""",
                (project_id,),
            ).fetchall()
            candidate_decisions = conn.execute(
                """SELECT vcd.*,u.display_name AS reviewer_name
                   FROM football_brief.visual_candidate_decisions vcd
                   JOIN football_brief.operator_users u ON u.operator_id=vcd.reviewer_operator_id
                   WHERE vcd.visual_project_id=%s ORDER BY vcd.created_at,vcd.id""",
                (project_id,),
            ).fetchall()
            shot_decisions = conn.execute(
                """SELECT vsd.*,u.display_name AS reviewer_name
                   FROM football_brief.visual_shot_decisions vsd
                   JOIN football_brief.operator_users u ON u.operator_id=vsd.reviewer_operator_id
                   WHERE vsd.visual_project_id=%s ORDER BY vsd.created_at,vsd.id""",
                (project_id,),
            ).fetchall()
            project_decisions = conn.execute(
                """SELECT vpd.*,u.display_name AS reviewer_name
                   FROM football_brief.visual_project_decisions vpd
                   JOIN football_brief.operator_users u ON u.operator_id=vpd.reviewer_operator_id
                   WHERE vpd.visual_project_id=%s ORDER BY vpd.created_at,vpd.id""",
                (project_id,),
            ).fetchall()
            events = conn.execute(
                """SELECT * FROM football_brief.visual_project_events
                   WHERE visual_project_id=%s ORDER BY created_at,id""",
                (project_id,),
            ).fetchall()
        return {
            "ok": True,
            "project": dict(project),
            "references": [dict(row) for row in references],
            "shots": [dict(row) for row in shots],
            "versions": [dict(row) for row in versions],
            "candidates": [dict(row) for row in candidates],
            "checks": [dict(row) for row in checks],
            "review_actions": [dict(row) for row in actions],
            "candidate_decisions": [dict(row) for row in candidate_decisions],
            "shot_decisions": [dict(row) for row in shot_decisions],
            "project_decisions": [dict(row) for row in project_decisions],
            "events": [dict(row) for row in events],
        }

    def project_for_content(self, *, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT id FROM football_brief.visual_projects
                   WHERE portfolio_content_id=%s ORDER BY created_at DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
        if not row:
            raise VisualProjectError("visual_project_not_found")
        return self.detail(project_id=row["id"])

    def register_candidate_result(
        self,
        *,
        candidate_id: UUID,
        result: CandidateResult,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            candidate = conn.execute(
                """SELECT vc.*,gj.status AS job_status,vs.visual_project_id
                   FROM football_brief.visual_candidates vc
                   JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=vc.generation_job_id
                   WHERE vc.id=%s FOR UPDATE OF vc""",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                raise VisualProjectError("visual_candidate_not_found")
            if candidate["status"] != "queued":
                raise VisualProjectError("visual_candidate_not_queued")
            if candidate["generation_job_id"] is not None and candidate["job_status"] != "succeeded":
                raise VisualProjectError(
                    "keyframe_job_not_succeeded",
                    details={"job_status": candidate["job_status"]},
                )
            if int(candidate["width"]) != result.width or int(candidate["height"]) != result.height:
                raise VisualProjectError(
                    "visual_candidate_dimension_mismatch",
                    details={
                        "requested": [int(candidate["width"]), int(candidate["height"])],
                        "registered": [result.width, result.height],
                    },
                )
            conn.execute(
                """UPDATE football_brief.visual_candidates
                   SET status='generated',asset_id=%s,mime_type=%s,provenance=%s::jsonb,
                       duplicate_candidate_id=%s,duplicate_similarity=%s
                   WHERE id=%s""",
                (
                    result.asset_id,
                    result.mime_type,
                    _json(result.provenance),
                    result.duplicate_candidate_id,
                    result.duplicate_similarity,
                    candidate_id,
                ),
            )
            for check in result.checks:
                conn.execute(
                    """INSERT INTO football_brief.visual_candidate_checks
                       (visual_candidate_id,check_type,status,score,evidence,checked_by)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s)""",
                    (
                        candidate_id,
                        check.check_type.value,
                        check.status.value,
                        check.score,
                        _json(check.evidence),
                        check.checked_by,
                    ),
                )
            aggregate = "pass" if all(check.status.value == "pass" for check in result.checks) else "fail"
            conn.execute(
                """UPDATE football_brief.visual_candidates SET checks_status=%s WHERE id=%s""",
                (aggregate, candidate_id),
            )
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_version_id,visual_candidate_id,event,actor,details)
                   VALUES (%s,%s,%s,'candidate_registered',%s,%s::jsonb)""",
                (
                    candidate["visual_project_id"],
                    candidate["visual_shot_version_id"],
                    candidate_id,
                    actor,
                    _json({"checks_status": aggregate, "asset_id": str(result.asset_id)}),
                ),
            )
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_version_id,visual_candidate_id,event,actor,details)
                   VALUES (%s,%s,%s,'candidate_checked',%s,%s::jsonb)""",
                (
                    candidate["visual_project_id"],
                    candidate["visual_shot_version_id"],
                    candidate_id,
                    actor,
                    _json({"required_check_count": len(result.checks), "checks_status": aggregate}),
                ),
            )
        return self.detail(project_id=candidate["visual_project_id"])

    def add_review_action(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        request: ReviewActionRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            shot = self._locked_shot(conn, project_id, shot_id, request.expected_shot_lock_version)
            if shot["current_version_id"] != request.visual_shot_version_id:
                raise VisualProjectError("stale_visual_shot_version")
            action = conn.execute(
                """INSERT INTO football_brief.visual_shot_review_actions
                   (visual_project_id,visual_shot_id,visual_shot_version_id,
                    visual_candidate_id,action_type,body,suggested_value,author_operator_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    project_id,
                    shot_id,
                    request.visual_shot_version_id,
                    request.visual_candidate_id,
                    request.action_type.value,
                    request.body,
                    request.suggested_value,
                    actor,
                ),
            ).fetchone()
            self._advance_shot_lock(
                conn,
                shot_id=shot_id,
                expected_lock=request.expected_shot_lock_version,
            )
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_id,visual_shot_version_id,
                    visual_candidate_id,event,actor,details)
                   VALUES (%s,%s,%s,%s,'review_action_created',%s,%s::jsonb)""",
                (
                    project_id,
                    shot_id,
                    request.visual_shot_version_id,
                    request.visual_candidate_id,
                    actor,
                    _json({"action_id": str(action["id"]), "action_type": request.action_type.value}),
                ),
            )
        return self.detail(project_id=project_id)

    def resolve_review_action(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        action_id: UUID,
        expected_shot_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            shot = self._locked_shot(conn, project_id, shot_id, expected_shot_lock_version)
            action = conn.execute(
                """UPDATE football_brief.visual_shot_review_actions
                   SET resolved_by_operator_id=%s,resolved_at=now()
                   WHERE id=%s AND visual_project_id=%s AND visual_shot_id=%s
                     AND resolved_at IS NULL RETURNING *""",
                (actor, action_id, project_id, shot_id),
            ).fetchone()
            if not action:
                raise VisualProjectError("visual_review_action_not_found_or_resolved")
            if action["visual_shot_version_id"] != shot["current_version_id"]:
                raise VisualProjectError("stale_visual_review_action")
            self._advance_shot_lock(conn, shot_id=shot_id, expected_lock=expected_shot_lock_version)
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_id,visual_shot_version_id,
                    visual_candidate_id,event,actor,details)
                   VALUES (%s,%s,%s,%s,'review_action_resolved',%s,%s::jsonb)""",
                (
                    project_id,
                    shot_id,
                    action["visual_shot_version_id"],
                    action["visual_candidate_id"],
                    actor,
                    _json({"action_id": str(action_id)}),
                ),
            )
        return self.detail(project_id=project_id)

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
            row = conn.execute(
                """SELECT vsv.*,sspe.*,vp.visual_preset_id,bvp.*
                   FROM football_brief.visual_shot_versions vsv
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   JOIN football_brief.script_scene_plan_entries sspe ON sspe.id=vs.scene_plan_entry_id
                   JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
                   JOIN football_brief.brand_visual_presets bvp ON bvp.id=vp.visual_preset_id
                   WHERE vsv.id=%s""",
                (shot["current_version_id"],),
            ).fetchone()
            references = conn.execute(
                """SELECT * FROM football_brief.visual_continuity_references
                   WHERE visual_project_id=%s AND active=true
                   ORDER BY reference_type,reference_key""",
                (project_id,),
            ).fetchall()
            compiled = self.compiler.compile(
                scene=dict(row),
                preset=dict(row),
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
                    int(row["version"]) + 1,
                    shot["current_version_id"],
                    compiled.prompt,
                    compiled.negative_prompt,
                    _json(compiled.components),
                    _json(compiled.reference_snapshot),
                    row["width"],
                    row["height"],
                    row["aspect_ratio"],
                    row["candidate_target_count"],
                    request.reason,
                    actor,
                    actor,
                ),
            )
            conn.execute(
                """UPDATE football_brief.visual_shots
                   SET current_version_id=%s,selected_candidate_id=NULL,status='working',
                       lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s""",
                (new_version_id, shot_id, request.expected_shot_lock_version),
            )
            conn.execute(
                """INSERT INTO football_brief.visual_project_events
                   (visual_project_id,visual_shot_id,visual_shot_version_id,event,actor,details)
                   VALUES (%s,%s,%s,'shot_revised',%s,%s::jsonb)""",
                (
                    project_id,
                    shot_id,
                    new_version_id,
                    actor,
                    _json({"parent_version_id": str(shot["current_version_id"]), "reason": request.reason}),
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

    def _ensure_project_candidates(
        self,
        *,
        project_id: UUID,
        base_seed: int,
        preferred_worker_id: str | None,
        timeout_seconds: int,
        max_attempts: int,
        actor: str,
    ) -> None:
        with self.database.connection() as conn:
            shots = conn.execute(
                "SELECT id FROM football_brief.visual_shots WHERE visual_project_id=%s ORDER BY sequence",
                (project_id,),
            ).fetchall()
        for shot in shots:
            self._ensure_shot_candidates(
                project_id=project_id,
                shot_id=shot["id"],
                base_seed=base_seed,
                preferred_worker_id=preferred_worker_id,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                actor=actor,
            )

    def _ensure_shot_candidates(
        self,
        *,
        project_id: UUID,
        shot_id: UUID,
        base_seed: int,
        preferred_worker_id: str | None,
        timeout_seconds: int,
        max_attempts: int,
        actor: str,
    ) -> None:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT vp.*,vs.id AS shot_id,vs.sequence AS shot_sequence,
                          vs.scene_plan_entry_id,vs.current_version_id,
                          vsv.compiled_prompt,vsv.negative_prompt,vsv.prompt_components,
                          vsv.reference_snapshot,vsv.width,vsv.height,vsv.candidate_target_count,
                          pw.id AS workflow_id,pw.current_version_id AS workflow_version_id
                   FROM football_brief.visual_projects vp
                   JOIN football_brief.visual_shots vs ON vs.visual_project_id=vp.id
                   JOIN football_brief.visual_shot_versions vsv ON vsv.id=vs.current_version_id
                   LEFT JOIN football_brief.production_workflows pw
                     ON pw.portfolio_content_id=vp.portfolio_content_id
                   WHERE vp.id=%s AND vs.id=%s""",
                (project_id, shot_id),
            ).fetchone()
            if not row:
                raise VisualProjectError("visual_shot_not_found")
            existing_ordinals = {
                int(item["ordinal"])
                for item in conn.execute(
                    "SELECT ordinal FROM football_brief.visual_candidates WHERE visual_shot_version_id=%s",
                    (row["current_version_id"],),
                ).fetchall()
            }
        for ordinal in range(1, int(row["candidate_target_count"]) + 1):
            if ordinal in existing_ordinals:
                continue
            seed = candidate_seed(base_seed, shot_sequence=int(row["shot_sequence"]), ordinal=ordinal)
            context = LocalVisualCandidateContext(
                portfolio_content_id=row["portfolio_content_id"],
                content_version=int(row["content_version"]),
                production_workflow_id=row["workflow_id"],
                production_workflow_version_id=row["workflow_version_id"],
                script_version_id=row["script_version_id"],
                visual_project_id=project_id,
                visual_shot_id=shot_id,
                visual_shot_version_id=row["current_version_id"],
                scene_plan_entry_id=row["scene_plan_entry_id"],
                candidate_ordinal=ordinal,
                seed=seed,
                provider=row["provider"],
                model_id=row["model_id"],
                width=int(row["width"]),
                height=int(row["height"]),
                prompt=row["compiled_prompt"],
                negative_prompt=row["negative_prompt"],
                prompt_components=dict(row["prompt_components"] or {}),
                reference_snapshot=list(row["reference_snapshot"] or []),
            )
            enqueue = self.keyframes.build_enqueue(
                context,
                actor=actor,
                preferred_worker_id=preferred_worker_id,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
            )
            job = self.jobs.enqueue(enqueue, actor=actor)
            with self.database.transaction() as conn:
                self._require_active_operator(conn, actor)
                existing = conn.execute(
                    "SELECT id FROM football_brief.visual_candidates WHERE generation_job_id=%s",
                    (job["id"],),
                ).fetchone()
                if existing:
                    continue
                candidate = conn.execute(
                    """INSERT INTO football_brief.visual_candidates
                       (visual_shot_version_id,ordinal,generation_job_id,provider,model_id,
                        seed,status,width,height,mime_type,prompt_snapshot,
                        negative_prompt_snapshot,reference_snapshot,provenance,
                        checks_status,actual_cost_usd,external_fee_incurred,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,'queued',%s,%s,'image/png',%s,%s,
                               %s::jsonb,'{}'::jsonb,'pending',0,false,%s)
                       RETURNING *""",
                    (
                        row["current_version_id"],
                        ordinal,
                        job["id"],
                        row["provider"],
                        row["model_id"],
                        seed,
                        row["width"],
                        row["height"],
                        row["compiled_prompt"],
                        row["negative_prompt"],
                        _json(row["reference_snapshot"] or []),
                        actor,
                    ),
                ).fetchone()
                conn.execute(
                    """INSERT INTO football_brief.visual_project_events
                       (visual_project_id,visual_shot_id,visual_shot_version_id,
                        visual_candidate_id,event,actor,details)
                       VALUES (%s,%s,%s,%s,'candidate_enqueued',%s,%s::jsonb)""",
                    (
                        project_id,
                        shot_id,
                        row["current_version_id"],
                        candidate["id"],
                        actor,
                        _json({"generation_job_id": str(job["id"]), "seed": seed, "ordinal": ordinal}),
                    ),
                )
        with self.database.transaction() as conn:
            version = conn.execute(
                "SELECT * FROM football_brief.visual_shot_versions WHERE id=%s FOR UPDATE",
                (row["current_version_id"],),
            ).fetchone()
            if version and version["status"] == "working":
                conn.execute(
                    "UPDATE football_brief.visual_shot_versions SET status='candidates_ready' WHERE id=%s",
                    (row["current_version_id"],),
                )
                conn.execute(
                    """UPDATE football_brief.visual_shots
                       SET status='candidates_ready',lock_version=lock_version+1
                       WHERE id=%s AND status='working'""",
                    (shot_id,),
                )

    def _initial_context(self, *, content_id: UUID, visual_preset_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id AS portfolio_content_id,pc.version AS content_version,
                          pc.brand_profile_id,sd.current_version_id AS script_version_id,
                          sv.status AS script_status,bvp.*
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
        if row["status"] != "active" or row["brand_profile_id"] != row["brand_profile_id"]:
            raise VisualProjectError("active_matching_visual_preset_required")
        return dict(row)

    @staticmethod
    def _locked_shot(conn, project_id: UUID, shot_id: UUID, expected_lock: int):
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
    def _advance_shot_lock(conn, *, shot_id: UUID, expected_lock: int) -> None:
        updated = conn.execute(
            """UPDATE football_brief.visual_shots
               SET lock_version=lock_version+1
               WHERE id=%s AND lock_version=%s RETURNING id""",
            (shot_id, expected_lock),
        ).fetchone()
        if not updated:
            raise VisualProjectError("visual_shot_conflict")

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (operator_id,),
        ).fetchone()
        if not row or not row["active"]:
            raise VisualProjectError("operator_inactive_or_missing")
