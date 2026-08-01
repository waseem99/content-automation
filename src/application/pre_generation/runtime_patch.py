from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.pre_generation.service import PreGenerationService, RULE_VERSION


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _validated_ensure_runs(
    self: PreGenerationService,
    *,
    campaign_id: UUID | None = None,
    actor: str,
) -> dict[str, Any]:
    """Create durable campaign runs with explicitly typed JSON metadata inputs."""

    with self.database.transaction() as conn:
        self._require_operator(conn, actor)
        conditions = [
            "item.state='activated'",
            "version.status='active'",
            "campaign.status='active'",
        ]
        values: list[Any] = []
        if campaign_id is not None:
            conditions.append("campaign.id=%s")
            values.append(campaign_id)
        inserted = conn.execute(
            f"""INSERT INTO football_brief.pre_generation_runs
                (campaign_item_id,autopilot_policy_id,status,current_stage,metadata)
                SELECT item.id,version.autopilot_policy_id,'queued','content_expansion',
                       jsonb_build_object(
                           'created_by',%s::text,
                           'campaign_id',campaign.id::text
                       )
                FROM football_brief.production_campaign_items item
                JOIN football_brief.production_campaign_versions version
                  ON version.id=item.campaign_version_id
                JOIN football_brief.production_campaigns campaign
                  ON campaign.id=version.campaign_id
                WHERE {' AND '.join(conditions)}
                ON CONFLICT (campaign_item_id) DO NOTHING
                RETURNING id""",
            (actor, *values),
        ).fetchall()
    return {
        "ok": True,
        "kind": "pre_generation_runs_ensured",
        "campaign_id": str(campaign_id) if campaign_id else None,
        "created": len(inserted),
    }


def _profile_and_family(
    self: PreGenerationService,
    *,
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    with self.database.connection() as conn:
        profile = conn.execute(
            """SELECT id,version,default_language,audience,tone,visual_rules,
                      content_restrictions,cadence,platforms,budget
               FROM football_brief.brand_profiles WHERE id=%s""",
            (context["brand_profile_id"],),
        ).fetchone()
        preset = conn.execute(
            """SELECT id,preset_key,display_name,role,approved_voice_id,language,speed,
                      style,pronunciation_rules,format_filters,topic_filters
               FROM football_brief.brand_narration_presets WHERE id=%s""",
            (context["narration_preset_id"],),
        ).fetchone()
        family = conn.execute(
            """SELECT id,content_family_id,parent_content_id,variant_type,primary_platform,
                      target_platforms,target_duration_seconds,short_cut_index,adaptation_profile,
                      scheduled_for,stage,version
               FROM football_brief.portfolio_content
               WHERE content_family_id=%s
               ORDER BY CASE variant_type WHEN 'master' THEN 0 WHEN 'adaptation' THEN 1 ELSE 2 END,
                        primary_platform,short_cut_index NULLS FIRST,id""",
            (context["content_family_id"],),
        ).fetchall()
    return (
        dict(profile or {}),
        dict(preset or {}),
        [dict(row) for row in family],
    )


def _timeline(scenes: list[dict[str, Any]], target_seconds: float) -> tuple[list[dict[str, Any]], bool, float]:
    ordered = sorted(scenes, key=lambda row: (int(row.get("position") or 0), str(row.get("scene_key") or "")))
    durations = [float(row.get("planned_duration_seconds") or 0) for row in ordered]
    total = sum(durations)
    correction = round(target_seconds - total, 3)
    corrected = False
    tolerance = max(2.0, target_seconds * 0.05)
    if ordered and abs(correction) > 0.01 and abs(correction) <= tolerance:
        candidate = durations[-1] + correction
        if candidate >= 1.0:
            durations[-1] = candidate
            total = sum(durations)
            corrected = True
    cursor = 0.0
    timeline: list[dict[str, Any]] = []
    for row, duration in zip(ordered, durations, strict=True):
        start = round(cursor, 3)
        end = round(cursor + duration, 3)
        timeline.append(
            {
                "scene_id": str(row.get("id")),
                "scene_key": str(row.get("scene_key")),
                "position": int(row.get("position") or 0),
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(duration, 3),
                "narration_text": str(row.get("narration_text") or "").strip(),
                "visual_intent": str(row.get("visual_intent") or "").strip(),
                "on_screen_text": str(row.get("on_screen_text") or "").strip(),
                "metadata": dict(row.get("metadata") or {}),
            }
        )
        cursor = end
    return timeline, corrected, round(target_seconds - total, 3)


def _renderer_shots(
    *,
    timeline: list[dict[str, Any]],
    context: dict[str, Any],
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    visual_rules = dict(profile.get("visual_rules") or {})
    restrictions = dict(profile.get("content_restrictions") or {})
    tone = str(profile.get("tone") or "clear, polished and brand-consistent")
    continuity = {
        "brand_profile_id": str(context.get("brand_profile_id")),
        "brand_profile_version": profile.get("version"),
        "content_family_id": str(context.get("content_family_id")),
        "visual_rules": visual_rules,
        "persistent_subjects": visual_rules.get("character_lock")
        or visual_rules.get("continuity")
        or visual_rules.get("subject_lock")
        or {},
    }
    generic_negative = [
        "generated readable text",
        "unapproved logos or watermarks",
        "copyrighted character resemblance",
        "celebrity likeness",
        "deformed anatomy or objects",
        "unmotivated camera shake",
        "abrupt cuts inside one shot",
        "visual elements prohibited by the brand profile",
    ]
    prohibited = restrictions.get("prohibited_visuals") or restrictions.get("disallowed_visuals") or []
    if isinstance(prohibited, str):
        prohibited = [part.strip() for part in prohibited.split(",") if part.strip()]
    negative = [*generic_negative, *[str(value) for value in prohibited]]
    shots: list[dict[str, Any]] = []
    for index, scene in enumerate(timeline, start=1):
        prompt = (
            f"Create one continuous {scene['duration_seconds']:.3f}-second production shot for "
            f"{context['brand_name']}. Purpose: {scene['visual_intent'] or scene['narration_text']}. "
            f"Narrative tone: {tone}. Preserve every continuity binding exactly. "
            f"Follow the approved visual rules: {_json(visual_rules)}. "
            "Use clear subject separation, intentional composition, natural motion and a controlled camera move. "
            "Leave safe space for editorial captions; do not generate captions inside the image. "
            "The shot must begin and end cleanly for deterministic editing."
        )
        shots.append(
            {
                "shot_id": f"S{index:03d}",
                "scene_key": scene["scene_key"],
                "start_seconds": scene["start_seconds"],
                "end_seconds": scene["end_seconds"],
                "duration_seconds": scene["duration_seconds"],
                "narration_text": scene["narration_text"],
                "editorial_on_screen_text": scene["on_screen_text"],
                "prompt": prompt,
                "negative_prompt": "; ".join(dict.fromkeys(negative)),
                "continuity_bindings": continuity,
                "generation_audio": False,
                "text_rendering": "editorial_post_only",
                "minimum_take_count": 1,
                "preferred_take_count": 2 if index in {1, 2, len(timeline)} else 1,
                "renderer_route": "unassigned_hybrid_router",
            }
        )
    return shots


def _validated_planning_stage(
    self: PreGenerationService,
    *,
    run: dict[str, Any],
    lease_token: UUID,
    actor: str,
    stage: str,
) -> dict[str, Any]:
    context = self._context(run["id"])
    detail = self.scripts.detail(document_id=UUID(str(context["script_document_id"])))
    current_id = str(detail["document"]["current_version_id"])
    version = next(row for row in detail["versions"] if str(row["id"]) == current_id)
    scenes = [row for row in detail["scenes"] if str(row["script_version_id"]) == current_id]
    profile, preset, family = _profile_and_family(self, context=context)
    target = float(context["target_duration_seconds"])
    timeline, duration_corrected, unresolved_delta = _timeline(scenes, target)
    if not timeline:
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code="scene_plan_empty",
            category="structural",
            severity="human_exception",
            details={"target_duration_seconds": target},
        )
    if abs(unresolved_delta) > 0.01:
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code="scene_duration_mismatch",
            category="duration",
            severity="human_exception",
            details={
                "target_duration_seconds": target,
                "planned_duration_seconds": round(sum(row["duration_seconds"] for row in timeline), 3),
                "unresolved_delta_seconds": unresolved_delta,
            },
        )

    if stage == "narration_plan":
        evidence = {
            "language": preset.get("language") or version["language"],
            "target_duration_seconds": target,
            "estimated_duration_seconds": float(version["estimated_duration_seconds"]),
            "preset_id": str(preset.get("id")) if preset else None,
            "preset_key": preset.get("preset_key"),
            "display_name": preset.get("display_name"),
            "role": preset.get("role"),
            "approved_voice_id": str(preset.get("approved_voice_id")) if preset.get("approved_voice_id") else None,
            "speed": float(preset.get("speed") or self._voice_profile(str(context["brand_slug"]))["speed"]),
            "style": dict(preset.get("style") or {}),
            "pronunciation_rules": dict(preset.get("pronunciation_rules") or {}),
            "segments": [
                {
                    "segment_id": row["scene_key"],
                    "start_seconds": row["start_seconds"],
                    "end_seconds": row["end_seconds"],
                    "duration_seconds": row["duration_seconds"],
                    "text": row["narration_text"],
                }
                for row in timeline
            ],
            "generated_audio": False,
        }
        next_stage = "scene_plan"
    elif stage == "scene_plan":
        evidence = {
            "scene_count": len(timeline),
            "exact_target_duration_seconds": target,
            "timeline_corrected": duration_corrected,
            "timeline": timeline,
            "shots": _renderer_shots(timeline=timeline, context=context, profile=profile),
            "continuity_binding": {
                "brand_profile_id": str(context["brand_profile_id"]),
                "brand_profile_version": profile.get("version"),
                "content_family_id": str(context["content_family_id"]),
                "visual_rules": dict(profile.get("visual_rules") or {}),
            },
            "generated_video": False,
        }
        next_stage = "caption_package"
    else:
        outputs = [
            {
                "content_id": str(row["id"]),
                "variant_type": row["variant_type"],
                "parent_content_id": str(row["parent_content_id"]) if row.get("parent_content_id") else None,
                "primary_platform": row["primary_platform"],
                "target_platforms": list(row.get("target_platforms") or []),
                "target_duration_seconds": int(row["target_duration_seconds"]),
                "short_cut_index": row.get("short_cut_index"),
                "adaptation_profile": dict(row.get("adaptation_profile") or {}),
                "caption": self._caption(context, version),
                "hashtags": self._hashtags(str(context["brand_slug"]), str(context["title"])),
                "thumbnail_copy": self._thumbnail_copy(str(context["title"])),
                "publishing_status": "not_ready",
            }
            for row in family
        ]
        evidence = {
            "master_title": context["title"],
            "primary_platform": context["primary_platform"],
            "target_platforms": list(context["target_platforms"] or []),
            "outputs": outputs,
            "output_count": len(outputs),
            "published": False,
        }
        next_stage = "final_generation_package"

    with self.database.transaction() as conn:
        self._owned_run_locked(conn, run["id"], lease_token)
        status = "corrected" if duration_corrected and stage == "scene_plan" else "passed"
        self._check(
            conn,
            run_id=run["id"],
            stage=stage,
            key=f"{stage}_frozen",
            status=status,
            score=100,
            evidence=evidence,
        )
        correction_sql = ",correction_count=correction_count+1" if status == "corrected" else ""
        conn.execute(
            f"""UPDATE football_brief.pre_generation_runs
                SET metadata=metadata || %s::jsonb{correction_sql} WHERE id=%s""",
            (_json({stage: evidence}), run["id"]),
        )
    return self._advance(
        run_id=run["id"],
        lease_token=lease_token,
        stage=next_stage,
        actor=actor,
        details={"planned_stage": stage, "automatic_correction": duration_corrected and stage == "scene_plan"},
    )


def install_pre_generation_runtime_patch() -> None:
    if getattr(PreGenerationService, "_typed_ensure_runs_installed", False):
        return
    PreGenerationService.ensure_runs = _validated_ensure_runs
    PreGenerationService._planning_stage = _validated_planning_stage
    PreGenerationService._typed_ensure_runs_installed = True
    PreGenerationService._renderer_ready_planning_installed = True


__all__ = ["install_pre_generation_runtime_patch"]
