"""Versioned brand operating profiles and fixed narration preset selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


ALLOWED_PRESET_ROLES = frozenset({"primary", "energetic", "serious"})


@dataclass(frozen=True, slots=True)
class NarrationSelection:
    profile_id: str
    profile_version: int
    preset_id: str
    preset_key: str
    role: str
    approved_voice_id: str
    provider: str
    provider_voice_id: str
    language: str
    speed: float
    style: dict[str, Any]
    pronunciation_rules: dict[str, Any]


def language_matches(allowed_languages: Iterable[str], requested: str) -> bool:
    requested_normalized = requested.strip().lower()
    requested_base = requested_normalized.split("-", 1)[0]
    allowed = {str(value).strip().lower() for value in allowed_languages}
    return requested_normalized in allowed or requested_base in allowed


def validate_profile_payload(payload: dict[str, Any]) -> None:
    language = str(payload.get("default_language") or "").strip()
    tone = str(payload.get("tone") or "").strip()
    platforms = [str(value).strip() for value in payload.get("platforms") or [] if str(value).strip()]
    budget = payload.get("budget") or {}
    if not language:
        raise ValueError("default_language is required")
    if len(tone) < 3:
        raise ValueError("tone must contain at least three characters")
    if not platforms:
        raise ValueError("at least one target platform is required")
    for field in ("audience", "visual_rules", "content_restrictions", "cadence", "budget"):
        if not isinstance(payload.get(field, {}), dict):
            raise ValueError(f"{field} must be an object")
    for name in ("monthly_local_usd", "monthly_managed_usd", "per_content_usd"):
        if name in budget and float(budget[name]) < 0:
            raise ValueError(f"{name} cannot be negative")


def validate_narration_presets(presets: list[dict[str, Any]]) -> None:
    if not 1 <= len(presets) <= 3:
        raise ValueError("a brand profile requires one to three narration presets")
    keys = [str(item.get("preset_key") or "") for item in presets]
    roles = [str(item.get("role") or "") for item in presets]
    if len(set(keys)) != len(keys):
        raise ValueError("narration preset keys must be unique")
    if len(set(roles)) != len(roles):
        raise ValueError("narration preset roles must be unique")
    if any(role not in ALLOWED_PRESET_ROLES for role in roles):
        raise ValueError("narration preset role must be primary, energetic, or serious")
    if sum(bool(item.get("is_default")) for item in presets) != 1:
        raise ValueError("exactly one narration preset must be the default")
    for item in presets:
        speed = float(item.get("speed", 1.0))
        if not 0.5 <= speed <= 2.0:
            raise ValueError("narration preset speed must be between 0.5 and 2.0")
        if not str(item.get("approved_voice_id") or "").strip():
            raise ValueError("approved_voice_id is required for every narration preset")
        if not str(item.get("language") or "").strip():
            raise ValueError("language is required for every narration preset")


def select_narration_preset(
    rows: list[dict[str, Any]],
    *,
    language: str,
    format_name: str | None = None,
    topic_type: str | None = None,
) -> dict[str, Any]:
    requested_language = language.strip().lower()
    requested_format = (format_name or "").strip().lower()
    requested_topic = (topic_type or "").strip().lower()
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for row in rows:
        if not bool(row.get("active", True)):
            continue
        if not language_matches([str(row.get("language") or "")], requested_language):
            continue
        formats = {str(value).strip().lower() for value in row.get("format_filters") or []}
        topics = {str(value).strip().lower() for value in row.get("topic_filters") or []}
        if formats and requested_format not in formats:
            continue
        if topics and requested_topic not in topics:
            continue
        score = 4 if str(row.get("language") or "").lower() == requested_language else 0
        score += 3 if formats and requested_format in formats else 0
        score += 3 if topics and requested_topic in topics else 0
        score += 1 if bool(row.get("is_default")) else 0
        role_priority = {"primary": "0", "energetic": "1", "serious": "2"}.get(str(row.get("role")), "9")
        candidates.append((score, role_priority + str(row.get("preset_key") or ""), row))
    if not candidates:
        raise ValueError("no eligible narration preset matches the requested language, format, and topic")
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


class BrandProfileService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def list_profiles(self, brand_id: UUID) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            profiles = conn.execute(
                "SELECT * FROM football_brief.brand_profiles WHERE brand_id=%s ORDER BY version DESC",
                (brand_id,),
            ).fetchall()
            result = []
            for profile in profiles:
                presets = conn.execute(
                    """SELECT p.*, v.provider, v.provider_voice_id, v.display_name AS voice_display_name,
                              v.approval_status AS voice_approval_status, v.expires_at AS voice_expires_at
                       FROM football_brief.brand_narration_presets p
                       JOIN football_brief.approved_voices v ON v.id=p.approved_voice_id
                       WHERE p.brand_profile_id=%s ORDER BY p.is_default DESC, p.role""",
                    (profile["id"],),
                ).fetchall()
                item = dict(profile)
                item["presets"] = [dict(row) for row in presets]
                result.append(item)
        return result

    def create_draft(
        self,
        *,
        brand_id: UUID,
        profile: dict[str, Any],
        presets: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        validate_profile_payload(profile)
        validate_narration_presets(presets)
        platforms = sorted({str(value).strip() for value in profile.get("platforms") or [] if str(value).strip()})
        with self.database.transaction() as conn:
            brand = conn.execute(
                "SELECT id FROM football_brief.brands WHERE id=%s FOR UPDATE", (brand_id,)
            ).fetchone()
            if not brand:
                return {"ok": False, "error": "brand_not_found"}
            version_row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM football_brief.brand_profiles WHERE brand_id=%s",
                (brand_id,),
            ).fetchone()
            version = int(version_row["version"])
            voice_rows: dict[str, dict[str, Any]] = {}
            for preset in presets:
                voice = self._approved_voice(conn, UUID(str(preset["approved_voice_id"])))
                self._validate_voice_for_preset(
                    voice=voice, language=str(preset["language"]), platforms=platforms
                )
                voice_rows[str(voice["id"])] = dict(voice)
            created = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id, version, default_language, audience, tone, visual_rules,
                    content_restrictions, cadence, platforms, budget, created_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    brand_id,
                    version,
                    profile["default_language"],
                    json.dumps(profile.get("audience") or {}),
                    profile["tone"],
                    json.dumps(profile.get("visual_rules") or {}),
                    json.dumps(profile.get("content_restrictions") or {}),
                    json.dumps(profile.get("cadence") or {}),
                    platforms,
                    json.dumps(profile.get("budget") or {}),
                    actor,
                ),
            ).fetchone()
            created_presets = []
            for preset in presets:
                row = conn.execute(
                    """INSERT INTO football_brief.brand_narration_presets
                       (brand_profile_id, preset_key, display_name, role, approved_voice_id,
                        language, speed, style, pronunciation_rules, format_filters,
                        topic_filters, is_default)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                       RETURNING *""",
                    (
                        created["id"],
                        preset["preset_key"],
                        preset["display_name"],
                        preset["role"],
                        preset["approved_voice_id"],
                        preset["language"],
                        float(preset.get("speed", 1.0)),
                        json.dumps(preset.get("style") or {}),
                        json.dumps(preset.get("pronunciation_rules") or {}),
                        sorted({str(value) for value in preset.get("format_filters") or []}),
                        sorted({str(value) for value in preset.get("topic_filters") or []}),
                        bool(preset.get("is_default")),
                    ),
                ).fetchone()
                item = dict(row)
                voice = voice_rows[str(row["approved_voice_id"])]
                item.update({"provider": voice["provider"], "provider_voice_id": voice["provider_voice_id"]})
                created_presets.append(item)
        return {"ok": True, "profile": dict(created), "presets": created_presets}

    def activate(self, *, brand_id: UUID, profile_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            brand = conn.execute(
                "SELECT id FROM football_brief.brands WHERE id=%s FOR UPDATE", (brand_id,)
            ).fetchone()
            if not brand:
                return {"ok": False, "error": "brand_not_found"}
            profile = conn.execute(
                """SELECT * FROM football_brief.brand_profiles
                   WHERE id=%s AND brand_id=%s FOR UPDATE""",
                (profile_id, brand_id),
            ).fetchone()
            if not profile:
                return {"ok": False, "error": "brand_profile_not_found"}
            if profile["status"] == "active":
                return {"ok": True, "profile": dict(profile), "already_active": True}
            if profile["status"] != "draft":
                return {"ok": False, "error": "only_draft_profiles_can_be_activated"}
            presets = conn.execute(
                """SELECT p.*, v.provider, v.provider_voice_id, v.approval_status,
                          v.allowed_languages, v.allowed_platforms, v.expires_at
                   FROM football_brief.brand_narration_presets p
                   JOIN football_brief.approved_voices v ON v.id=p.approved_voice_id
                   WHERE p.brand_profile_id=%s AND p.active=true ORDER BY p.role""",
                (profile_id,),
            ).fetchall()
            preset_dicts = [dict(row) for row in presets]
            validate_narration_presets(preset_dicts)
            for preset in preset_dicts:
                self._validate_voice_for_preset(
                    voice=preset,
                    language=str(preset["language"]),
                    platforms=list(profile["platforms"] or []),
                )
            conn.execute(
                """UPDATE football_brief.brand_profiles SET status='retired'
                   WHERE brand_id=%s AND status='active' AND id<>%s""",
                (brand_id, profile_id),
            )
            activated = conn.execute(
                """UPDATE football_brief.brand_profiles
                   SET status='active', activated_by=%s, activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, profile_id),
            ).fetchone()
        return {"ok": True, "profile": dict(activated), "presets": preset_dicts}

    def select(
        self,
        *,
        brand_id: UUID,
        language: str | None = None,
        format_name: str | None = None,
        topic_type: str | None = None,
    ) -> NarrationSelection:
        requested_language: str
        with self.database.connection() as conn:
            profile = conn.execute(
                "SELECT * FROM football_brief.brand_profiles WHERE brand_id=%s AND status='active'",
                (brand_id,),
            ).fetchone()
            if not profile:
                raise ValueError("brand has no active profile")
            requested_language = language or str(profile["default_language"])
            rows = conn.execute(
                """SELECT p.*, v.provider, v.provider_voice_id, v.approval_status,
                          v.allowed_languages, v.allowed_platforms, v.expires_at
                   FROM football_brief.brand_narration_presets p
                   JOIN football_brief.approved_voices v ON v.id=p.approved_voice_id
                   WHERE p.brand_profile_id=%s AND p.active=true
                     AND v.approval_status='approved'
                     AND (v.expires_at IS NULL OR v.expires_at > now())""",
                (profile["id"],),
            ).fetchall()
        eligible = []
        for raw in rows:
            row = dict(raw)
            try:
                self._validate_voice_for_preset(
                    voice=row,
                    language=str(row["language"]),
                    platforms=list(profile["platforms"] or []),
                )
            except ValueError:
                continue
            eligible.append(row)
        selected = select_narration_preset(
            eligible,
            language=requested_language,
            format_name=format_name,
            topic_type=topic_type,
        )
        return NarrationSelection(
            profile_id=str(profile["id"]),
            profile_version=int(profile["version"]),
            preset_id=str(selected["id"]),
            preset_key=str(selected["preset_key"]),
            role=str(selected["role"]),
            approved_voice_id=str(selected["approved_voice_id"]),
            provider=str(selected["provider"]),
            provider_voice_id=str(selected["provider_voice_id"]),
            language=str(selected["language"]),
            speed=float(selected["speed"]),
            style=dict(selected.get("style") or {}),
            pronunciation_rules=dict(selected.get("pronunciation_rules") or {}),
        )

    def bind_content(self, *, content_id: UUID, preset_id: UUID) -> dict[str, Any]:
        with self.database.transaction() as conn:
            content = conn.execute(
                """SELECT pc.*, mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s FOR UPDATE""",
                (content_id,),
            ).fetchone()
            if not content:
                return {"ok": False, "error": "content_not_found"}
            preset = conn.execute(
                """SELECT p.*, bp.brand_id, bp.status AS profile_status, bp.platforms,
                          v.approval_status, v.allowed_languages, v.allowed_platforms, v.expires_at
                   FROM football_brief.brand_narration_presets p
                   JOIN football_brief.brand_profiles bp ON bp.id=p.brand_profile_id
                   JOIN football_brief.approved_voices v ON v.id=p.approved_voice_id
                   WHERE p.id=%s""",
                (preset_id,),
            ).fetchone()
            if not preset:
                return {"ok": False, "error": "narration_preset_not_found"}
            if str(preset["brand_id"]) != str(content["brand_id"]):
                return {"ok": False, "error": "narration_preset_brand_mismatch"}
            if preset["profile_status"] != "active" or not preset["active"]:
                return {"ok": False, "error": "narration_preset_not_active"}
            try:
                self._validate_voice_for_preset(
                    voice=dict(preset),
                    language=str(preset["language"]),
                    platforms=list(preset["platforms"] or []),
                )
            except ValueError:
                return {"ok": False, "error": "narration_preset_voice_not_eligible"}
            if content["brand_profile_id"] is not None or content["narration_preset_id"] is not None:
                if (
                    str(content["brand_profile_id"]) == str(preset["brand_profile_id"])
                    and str(content["narration_preset_id"]) == str(preset_id)
                ):
                    return {"ok": True, "item": dict(content), "already_pinned": True}
                return {"ok": False, "error": "narration_selection_already_pinned"}
            updated = conn.execute(
                """UPDATE football_brief.portfolio_content
                   SET brand_profile_id=%s, narration_preset_id=%s
                   WHERE id=%s RETURNING *""",
                (preset["brand_profile_id"], preset_id, content_id),
            ).fetchone()
        return {"ok": True, "item": dict(updated), "already_pinned": False}

    @staticmethod
    def _approved_voice(conn, approved_voice_id: UUID):
        voice = conn.execute(
            """SELECT * FROM football_brief.approved_voices
               WHERE id=%s AND approval_status='approved'
                 AND (expires_at IS NULL OR expires_at > now())""",
            (approved_voice_id,),
        ).fetchone()
        if not voice:
            raise ValueError("narration preset must reference a currently approved voice")
        return voice

    @staticmethod
    def _validate_voice_for_preset(
        *, voice: dict[str, Any], language: str, platforms: list[str]
    ) -> None:
        if str(voice.get("approval_status")) != "approved":
            raise ValueError("narration preset voice is not approved")
        expires_at = voice.get("expires_at")
        if expires_at is not None:
            now = datetime.now(timezone.utc)
            expiry = expires_at if getattr(expires_at, "tzinfo", None) else expires_at.replace(tzinfo=timezone.utc)
            if expiry <= now:
                raise ValueError("narration preset voice approval has expired")
        if not language_matches(voice.get("allowed_languages") or [], language):
            raise ValueError("narration preset language is not allowed for the approved voice")
        allowed_platforms = {str(value) for value in voice.get("allowed_platforms") or []}
        if allowed_platforms and not set(platforms).issubset(allowed_platforms):
            raise ValueError("approved voice does not cover every brand platform")
