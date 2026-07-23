from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from typing import Any

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


BRANDS = (
    {
        "slug": "rawr-nation",
        "display_name": "Rawr Nation",
        "niche": "Original wildlife facts and visual science",
        "target": 30,
        "pillars": ["animal senses", "survival mechanisms", "myth versus evidence", "behaviour reveals"],
        "tone": "fast, surprising, factual, cinematic, accessible",
    },
    {
        "slug": "animal-x",
        "display_name": "Animal X",
        "niche": "Animal behaviour, anatomy, and field discoveries",
        "target": 24,
        "pillars": ["hidden signals", "social intelligence", "anatomy in action", "field discoveries"],
        "tone": "curious, factual, premium documentary, emotionally restrained",
    },
)
OPERATORS = (
    ("LOCAL_ADMIN_OPERATOR_ID", "local-admin", "Local Administrator", "admin"),
    ("LOCAL_PRODUCER_OPERATOR_ID", "local-producer", "Local Producer", "producer"),
    ("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer", "Local Reviewer", "reviewer"),
    ("LOCAL_PUBLISHER_OPERATOR_ID", "local-publisher", "Local Publisher", "publisher"),
)


def month_start() -> date:
    raw = os.getenv("LOCAL_PLAN_MONTH", "").strip()
    value = date.fromisoformat(raw) if raw else date.today().replace(day=1)
    if value.day != 1:
        raise ValueError("LOCAL_PLAN_MONTH must be the first day of a month")
    return value


class LocalOnboarding:
    """Idempotently seed the two pilot brands without storing authentication keys."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.admin_id = os.getenv("LOCAL_ADMIN_OPERATOR_ID", "local-admin")
        self.voice = os.getenv("KOKORO_VOICE", "af_heart")
        self.voice_model = os.getenv("KOKORO_MODEL_ID", "hexgrad/Kokoro-82M")
        self.plan_month = month_start()

    def run(self) -> dict[str, Any]:
        with self.database.transaction() as conn:
            operators = self._operators(conn)
            brands = self._brands(conn)
            voice = self._voice(conn)
            profiles, plans, samples = {}, {}, {}
            for spec in BRANDS:
                brand = brands[spec["slug"]]
                profile = self._profile(conn, brand, spec, voice)
                plan = self._plan(conn, brand, spec)
                sample = self._sample(conn, plan, profile, spec)
                profiles[spec["slug"]], plans[spec["slug"]], samples[spec["slug"]] = profile, plan, sample
            for operator in operators.values():
                for brand in brands.values():
                    conn.execute(
                        """INSERT INTO football_brief.operator_brand_assignments
                           (operator_user_id,brand_id,assigned_by)
                           VALUES (%s,%s,%s)
                           ON CONFLICT DO NOTHING""",
                        (operator["id"], brand["id"], self.admin_id),
                    )
        return {
            "ok": True,
            "kind": "local_production_onboarding",
            "operators": {key: {"operator_id": row["operator_id"], "roles": row["roles"]} for key, row in operators.items()},
            "brands": {key: {"id": str(row["id"]), "name": row["display_name"]} for key, row in brands.items()},
            "profiles": {key: {"id": str(row["id"]), "version": row["version"]} for key, row in profiles.items()},
            "plans": {key: {"id": str(row["id"]), "month_start": str(row["month_start"])} for key, row in plans.items()},
            "sample_content": {key: {"id": str(row["id"]), "title": row["title"]} for key, row in samples.items()},
            "voice": {"id": str(voice["id"]), "voice": self.voice, "model": self.voice_model},
            "operator_keys_stored_in_database": False,
            "managed_renderer_enabled": False,
            "live_publishing_enabled": False,
        }

    def _operators(self, conn: Any) -> dict[str, dict[str, Any]]:
        output = {}
        for env_name, default_id, default_name, role in OPERATORS:
            operator_id = os.getenv(env_name, default_id)
            display_name = os.getenv(env_name.replace("_ID", "_DISPLAY_NAME"), default_name)
            row = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id,display_name,active,created_by)
                   VALUES (%s,%s,true,%s)
                   ON CONFLICT (operator_id) DO UPDATE SET display_name=EXCLUDED.display_name,active=true
                   RETURNING *""",
                (operator_id, display_name, self.admin_id),
            ).fetchone()
            conn.execute("DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s", (row["id"],))
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id,role,assigned_by) VALUES (%s,%s,%s)""",
                (row["id"], role, self.admin_id),
            )
            output[operator_id] = {**dict(row), "roles": [role]}
        return output

    def _brands(self, conn: Any) -> dict[str, dict[str, Any]]:
        output = {}
        for spec in BRANDS:
            row = conn.execute(
                """INSERT INTO football_brief.brands
                   (slug,display_name,niche,primary_platform,content_mode,monthly_target,
                    source_links,content_pillars,active,metadata)
                   VALUES (%s,%s,%s,'facebook','video',%s,'[]'::jsonb,%s::jsonb,true,%s::jsonb)
                   ON CONFLICT (slug) DO UPDATE SET
                     display_name=EXCLUDED.display_name,niche=EXCLUDED.niche,
                     monthly_target=EXCLUDED.monthly_target,content_pillars=EXCLUDED.content_pillars,
                     active=true,metadata=football_brief.brands.metadata || EXCLUDED.metadata
                   RETURNING *""",
                (
                    spec["slug"], spec["display_name"], spec["niche"], spec["target"],
                    json.dumps(spec["pillars"]),
                    json.dumps({"local_onboarding": True, "cadence": f"{spec['target']} masters monthly"}),
                ),
            ).fetchone()
            output[spec["slug"]] = dict(row)
        return output

    def _voice(self, conn: Any) -> dict[str, Any]:
        return dict(conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider,provider_voice_id,display_name,voice_type,approval_status,
                allowed_languages,allowed_platforms,prohibited_uses,approved_by,approved_at,metadata)
               VALUES ('kokoro',%s,%s,'premade','approved',
                       ARRAY['en','en-US']::text[],
                       ARRAY['facebook','youtube','youtube_shorts','tiktok','instagram']::text[],
                       ARRAY['impersonation','deceptive_synthetic_media']::text[],
                       %s,now(),%s::jsonb)
               ON CONFLICT (provider,provider_voice_id) DO UPDATE SET
                 approval_status='approved',approved_by=EXCLUDED.approved_by,approved_at=now(),
                 metadata=football_brief.approved_voices.metadata || EXCLUDED.metadata
               RETURNING *""",
            (
                self.voice, f"Kokoro {self.voice}", self.admin_id,
                json.dumps({"model_id": self.voice_model, "local_only": True, "commercial_review_required": True}),
            ),
        ).fetchone())

    def _profile(self, conn: Any, brand: dict[str, Any], spec: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
        active = conn.execute(
            "SELECT * FROM football_brief.brand_profiles WHERE brand_id=%s AND status='active'",
            (brand["id"],),
        ).fetchone()
        if active:
            return dict(active)
        draft = conn.execute(
            """SELECT * FROM football_brief.brand_profiles
               WHERE brand_id=%s AND status='draft' ORDER BY version DESC LIMIT 1 FOR UPDATE""",
            (brand["id"],),
        ).fetchone()
        if not draft:
            version = conn.execute(
                "SELECT COALESCE(max(version),0)+1 AS v FROM football_brief.brand_profiles WHERE brand_id=%s",
                (brand["id"],),
            ).fetchone()["v"]
            draft = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id,version,status,default_language,audience,tone,visual_rules,
                    content_restrictions,cadence,platforms,budget,created_by)
                   VALUES (%s,%s,'draft','en-US',%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                           ARRAY['facebook','youtube_shorts','tiktok']::text[],%s::jsonb,%s)
                   RETURNING *""",
                (
                    brand["id"], version,
                    json.dumps({"primary": "English-speaking wildlife and science audiences"}),
                    spec["tone"],
                    json.dumps({"aspect_ratio": "9:16", "original_assets_only": True, "keyframe_provider": "comfyui-sdxl-local"}),
                    json.dumps({"factual_claims_need_sources": True, "human_approval_required": True}),
                    json.dumps({"monthly_target": spec["target"]}),
                    json.dumps({"local_generation_default": True, "managed_monthly_limit_usd": 0}),
                    self.admin_id,
                ),
            ).fetchone()
        preset = conn.execute(
            "SELECT id FROM football_brief.brand_narration_presets WHERE brand_profile_id=%s AND preset_key='default'",
            (draft["id"],),
        ).fetchone()
        if not preset:
            conn.execute(
                """INSERT INTO football_brief.brand_narration_presets
                   (brand_profile_id,preset_key,display_name,role,approved_voice_id,language,
                    speed,style,pronunciation_rules,format_filters,topic_filters,is_default,active)
                   VALUES (%s,'default','Default local narration','primary',%s,'en-US',1.0,
                           %s::jsonb,'{}'::jsonb,ARRAY['vertical_short']::text[],ARRAY[]::text[],true,true)""",
                (draft["id"], voice["id"], json.dumps({"delivery": "clear factual documentary"})),
            )
        return dict(conn.execute(
            """UPDATE football_brief.brand_profiles
               SET status='active',activated_by=%s,activated_at=now()
               WHERE id=%s AND status='draft' RETURNING *""",
            (self.admin_id, draft["id"]),
        ).fetchone())

    def _plan(self, conn: Any, brand: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        return dict(conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id,month_start,target_count,status,strategy,created_by)
               VALUES (%s,%s,%s,'draft',%s::jsonb,%s)
               ON CONFLICT (brand_id,month_start) DO UPDATE SET
                 target_count=EXCLUDED.target_count,
                 strategy=football_brief.monthly_content_plans.strategy || EXCLUDED.strategy
               RETURNING *""",
            (
                brand["id"], self.plan_month, spec["target"],
                json.dumps({"local_first": True, "human_review": True, "managed_renderer": "not_configured"}),
                self.admin_id,
            ),
        ).fetchone())

    def _sample(self, conn: Any, plan: dict[str, Any], profile: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        preset = conn.execute(
            """SELECT * FROM football_brief.brand_narration_presets
               WHERE brand_profile_id=%s AND is_default AND active""",
            (profile["id"],),
        ).fetchone()
        semantic = f"local-smoke-{spec['slug']}"
        existing = conn.execute(
            "SELECT * FROM football_brief.portfolio_content WHERE plan_id=%s AND semantic_key=%s",
            (plan["id"], semantic),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE football_brief.portfolio_content
                   SET brand_profile_id=COALESCE(brand_profile_id,%s),
                       narration_preset_id=COALESCE(narration_preset_id,%s)
                   WHERE id=%s""",
                (profile["id"], preset["id"], existing["id"]),
            )
            return dict(conn.execute("SELECT * FROM football_brief.portfolio_content WHERE id=%s", (existing["id"],)).fetchone())
        fingerprint = hashlib.sha256(f"local-smoke:{spec['slug']}:v1".encode()).hexdigest()
        return dict(conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id,scheduled_for,title,concept,format,stage,concept_fingerprint,semantic_key,
                version,brand_profile_id,narration_preset_id,metadata)
               VALUES (%s,%s,%s,%s,'vertical_short','idea',%s,%s,1,%s,%s,%s::jsonb)
               RETURNING *""",
            (
                plan["id"], self.plan_month, f"Local production smoke — {spec['display_name']}",
                f"Create an original 35–45 second {spec['display_name']} explainer with sources, local narration, and reviewable keyframes.",
                fingerprint, semantic, profile["id"], preset["id"],
                json.dumps({"local_smoke_fixture": True, "automatic_approval": False, "automatic_publication": False}),
            ),
        ).fetchone())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the local multi-brand production workspace.")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        result = LocalOnboarding(database).run()
    finally:
        database.close()
    print(json.dumps(result, default=str, sort_keys=True, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
