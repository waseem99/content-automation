from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.application.visuals.models import VisualPresetRequest

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class VisualPresetError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class VisualPresetService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def create(
        self,
        *,
        brand_profile_id: UUID,
        request: VisualPresetRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            profile = conn.execute(
                """SELECT bp.*,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.brand_profiles bp
                   JOIN football_brief.brands b ON b.id=bp.brand_id
                   WHERE bp.id=%s""",
                (brand_profile_id,),
            ).fetchone()
            if not profile:
                raise VisualPresetError("brand_profile_not_found")
            latest = conn.execute(
                """SELECT * FROM football_brief.brand_visual_presets
                   WHERE brand_profile_id=%s AND preset_key=%s
                   ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (brand_profile_id, request.preset_key),
            ).fetchone()
            if latest and request.parent_preset_id is None:
                raise VisualPresetError(
                    "visual_preset_parent_required",
                    details={"latest_preset_id": str(latest["id"]), "latest_version": int(latest["version"])},
                )
            version = 1
            if request.parent_preset_id is not None:
                parent = conn.execute(
                    """SELECT * FROM football_brief.brand_visual_presets
                       WHERE id=%s AND brand_profile_id=%s AND preset_key=%s""",
                    (request.parent_preset_id, brand_profile_id, request.preset_key),
                ).fetchone()
                if not parent:
                    raise VisualPresetError("visual_preset_parent_not_found")
                if latest and parent["id"] != latest["id"]:
                    raise VisualPresetError("visual_preset_parent_is_not_latest")
                version = int(parent["version"]) + 1
            row = conn.execute(
                """INSERT INTO football_brief.brand_visual_presets
                   (brand_profile_id,preset_key,display_name,version,parent_preset_id,
                    status,palette,subject_rules,environment_rules,camera_rules,
                    lighting_rules,framing_rules,negative_prompt,exclusions,created_by)
                   VALUES (%s,%s,%s,%s,%s,'draft',%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    brand_profile_id,
                    request.preset_key,
                    request.display_name,
                    version,
                    request.parent_preset_id,
                    _json(request.palette),
                    _json(request.subject_rules),
                    _json(request.environment_rules),
                    _json(request.camera_rules),
                    _json(request.lighting_rules),
                    _json(request.framing_rules),
                    request.negative_prompt,
                    _json(request.exclusions),
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "preset": dict(row), "brand": dict(profile)}

    def activate(self, *, preset_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            preset = conn.execute(
                "SELECT * FROM football_brief.brand_visual_presets WHERE id=%s FOR UPDATE",
                (preset_id,),
            ).fetchone()
            if not preset:
                raise VisualPresetError("visual_preset_not_found")
            if preset["status"] == "active":
                return {"ok": True, "preset": dict(preset), "already_active": True}
            if preset["status"] != "draft":
                raise VisualPresetError("visual_preset_not_draft")
            conn.execute(
                """UPDATE football_brief.brand_visual_presets
                   SET status='retired'
                   WHERE brand_profile_id=%s AND preset_key=%s AND status='active'""",
                (preset["brand_profile_id"], preset["preset_key"]),
            )
            activated = conn.execute(
                """UPDATE football_brief.brand_visual_presets
                   SET status='active',activated_at=now()
                   WHERE id=%s AND status='draft' RETURNING *""",
                (preset_id,),
            ).fetchone()
            if not activated:
                raise VisualPresetError("visual_preset_activation_conflict")
        return {"ok": True, "preset": dict(activated), "already_active": False}

    def list_for_profile(self, *, brand_profile_id: UUID) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.brand_visual_presets
                   WHERE brand_profile_id=%s ORDER BY preset_key,version DESC""",
                (brand_profile_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (operator_id,),
        ).fetchone()
        if not row or not row["active"]:
            raise VisualPresetError("operator_inactive_or_missing")
