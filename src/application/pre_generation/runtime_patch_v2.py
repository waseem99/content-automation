from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.pre_generation.runtime_patch import (
    _json,
    _profile_and_family,
    _renderer_shots,
)
from src.application.pre_generation.service import PreGenerationService


def _canonical_timeline(
    scenes: list[dict[str, Any]],
    target_seconds: float,
) -> tuple[list[dict[str, Any]], bool, float]:
    """Build the exact timeline from the canonical P89 scene columns.

    Script scenes are stored as ``sequence``, ``visual_brief`` and
    ``target_duration_seconds``. The first renderer-ready implementation used
    presentation aliases that do not exist in PostgreSQL, causing valid scenes
    to appear as zero-duration rows. This adapter intentionally binds directly
    to the canonical schema.
    """

    ordered = sorted(
        scenes,
        key=lambda row: (
            int(row.get("sequence") or 0),
            str(row.get("scene_key") or ""),
        ),
    )
    durations = [float(row.get("target_duration_seconds") or 0) for row in ordered]
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
                "sequence": int(row.get("sequence") or 0),
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(duration, 3),
                "narration_text": str(row.get("narration_text") or "").strip(),
                "visual_intent": str(row.get("visual_brief") or "").strip(),
                "on_screen_text": str(row.get("on_screen_text") or "").strip(),
            }
        )
        cursor = end
    return timeline, corrected, round(target_seconds - total, 3)


def _canonical_planning_stage(
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
    version = next(
        row for row in detail["versions"] if str(row["id"]) == current_id
    )
    scenes = [
        row
        for row in detail["scenes"]
        if str(row["script_version_id"]) == current_id
    ]
    profile, preset, family = _profile_and_family(self, context=context)
    target = float(context["target_duration_seconds"])
    timeline, duration_corrected, unresolved_delta = _canonical_timeline(
        scenes,
        target,
    )
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
                "planned_duration_seconds": round(
                    sum(row["duration_seconds"] for row in timeline),
                    3,
                ),
                "unresolved_delta_seconds": unresolved_delta,
            },
        )

    if stage == "narration_plan":
        evidence = {
            "language": preset.get("language") or version["language"],
            "target_duration_seconds": target,
            "estimated_duration_seconds": float(
                version["estimated_duration_seconds"]
            ),
            "preset_id": str(preset.get("id")) if preset else None,
            "preset_key": preset.get("preset_key"),
            "display_name": preset.get("display_name"),
            "role": preset.get("role"),
            "approved_voice_id": (
                str(preset.get("approved_voice_id"))
                if preset.get("approved_voice_id")
                else None
            ),
            "speed": float(
                preset.get("speed")
                or self._voice_profile(str(context["brand_slug"]))["speed"]
            ),
            "style": dict(preset.get("style") or {}),
            "pronunciation_rules": dict(
                preset.get("pronunciation_rules") or {}
            ),
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
            "shots": _renderer_shots(
                timeline=timeline,
                context=context,
                profile=profile,
            ),
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
                "parent_content_id": (
                    str(row["parent_content_id"])
                    if row.get("parent_content_id")
                    else None
                ),
                "primary_platform": row["primary_platform"],
                "target_platforms": list(row.get("target_platforms") or []),
                "target_duration_seconds": int(
                    row["target_duration_seconds"]
                ),
                "short_cut_index": row.get("short_cut_index"),
                "adaptation_profile": dict(
                    row.get("adaptation_profile") or {}
                ),
                "caption": self._caption(context, version),
                "hashtags": self._hashtags(
                    str(context["brand_slug"]),
                    str(context["title"]),
                ),
                "thumbnail_copy": self._thumbnail_copy(
                    str(context["title"])
                ),
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
        status = (
            "corrected"
            if duration_corrected and stage == "scene_plan"
            else "passed"
        )
        self._check(
            conn,
            run_id=run["id"],
            stage=stage,
            key=f"{stage}_frozen",
            status=status,
            score=100,
            evidence=evidence,
        )
        correction_sql = (
            ",correction_count=correction_count+1"
            if status == "corrected"
            else ""
        )
        conn.execute(
            f"""UPDATE football_brief.pre_generation_runs
                SET metadata=metadata || %s::jsonb{correction_sql}
                WHERE id=%s""",
            (_json({stage: evidence}), run["id"]),
        )
    return self._advance(
        run_id=run["id"],
        lease_token=lease_token,
        stage=next_stage,
        actor=actor,
        details={
            "planned_stage": stage,
            "automatic_correction": (
                duration_corrected and stage == "scene_plan"
            ),
        },
    )


def install_pre_generation_schema_alignment_patch() -> None:
    if getattr(
        PreGenerationService,
        "_canonical_scene_schema_patch_installed",
        False,
    ):
        return
    PreGenerationService._planning_stage = _canonical_planning_stage
    PreGenerationService._canonical_scene_schema_patch_installed = True


__all__ = [
    "install_pre_generation_schema_alignment_patch",
]
