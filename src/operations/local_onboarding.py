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
        "display_name": "Rawr Nation TV",
        "facebook_url": "https://www.facebook.com/RawrNationTV",
        "niche": "Original wildlife facts and visual science",
        "target": 30,
        "pillars": ["animal senses", "survival mechanisms", "myth versus evidence", "behaviour reveals"],
        "tone": "fast, surprising, factual, cinematic, accessible",
    },
    {
        "slug": "animal-x",
        "display_name": "Animal X",
        "facebook_url": "https://www.facebook.com/people/Animal-X/61566325046583/",
        "niche": "Animal behaviour, anatomy, and field discoveries",
        "target": 24,
        "pillars": ["hidden signals", "social intelligence", "anatomy in action", "field discoveries"],
        "tone": "curious, factual, premium documentary, emotionally restrained",
    },
    {
        "slug": "ani-films",
        "display_name": "Ani Films",
        "facebook_url": "https://www.facebook.com/people/Ani-Films/61563298430902/",
        "niche": "Cinematic animal stories, behaviour and conservation explainers",
        "target": 24,
        "pillars": ["animal stories", "behaviour explained", "conservation context", "cinematic discoveries"],
        "tone": "cinematic, warm, factual, visual-first, emotionally engaging without exaggeration",
    },
    {
        "slug": "historiq",
        "display_name": "Historiq",
        "facebook_url": "https://www.facebook.com/people/Historiq/61580906280508/",
        "niche": "Evidence-led history, overlooked events and historical comparisons",
        "target": 24,
        "pillars": ["overlooked history", "myth versus record", "turning points", "then and now"],
        "tone": "authoritative, curious, cinematic, evidence-led, clear and non-sensational",
    },
)

OPERATORS = (
    ("LOCAL_ADMIN_OPERATOR_ID", "local-admin", "Local Administrator", "admin"),
    ("LOCAL_PRODUCER_OPERATOR_ID", "local-producer", "Local Producer", "producer"),
    ("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer", "Local Reviewer", "reviewer"),
    ("LOCAL_PUBLISHER_OPERATOR_ID", "local-publisher", "Local Publisher", "publisher"),
)

PLATFORMS = ["facebook", "instagram", "tiktok", "youtube", "youtube_shorts"]
FORMATS = ["vertical_short", "explainer", "master_video", "adaptation", "short_cut"]


def month_start() -> date:
    raw = os.getenv("LOCAL_PLAN_MONTH", "").strip()
    value = date.fromisoformat(raw) if raw else date.today().replace(day=1)
    if value.day != 1:
        raise ValueError("LOCAL_PLAN_MONTH must be the first day of a month")
    return value


class LocalOnboarding:
    """Idempotently seed the local four-brand workspace without storing authentication keys."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.admin_id = os.getenv("LOCAL_ADMIN_OPERATOR_ID", "local-admin")
        self.voice_model = os.getenv("KOKORO_MODEL_ID", "hexgrad/Kokoro-82M")
        self.voice_specs = (
            {
                "key": "default",
                "role": "primary",
                "voice": os.getenv("KOKORO_PRIMARY_VOICE", os.getenv("KOKORO_VOICE", "af_heart")),
                "display_name": "Primary documentary voice",
                "speed": 1.0,
                "style": {"delivery": "clear factual documentary", "energy": "balanced"},
                "is_default": True,
            },
            {
                "key": "energetic",
                "role": "energetic",
                "voice": os.getenv("KOKORO_ENERGETIC_VOICE", "af_bella"),
                "display_name": "Energetic social voice",
                "speed": 1.06,
                "style": {"delivery": "energetic factual social", "energy": "high but controlled"},
                "is_default": False,
            },
            {
                "key": "serious",
                "role": "serious",
                "voice": os.getenv("KOKORO_SERIOUS_VOICE", "am_adam"),
                "display_name": "Serious documentary voice",
                "speed": 0.96,
                "style": {"delivery": "measured premium documentary", "energy": "restrained"},
                "is_default": False,
            },
        )
        self.plan_month = month_start()

    def run(self) -> dict[str, Any]:
        with self.database.transaction() as conn:
            operators = self._operators(conn)
            brands = self._brands(conn)
            voices = self._voices(conn)
            profiles, plans, samples = {}, {}, {}
            for spec in BRANDS:
                brand = brands[spec["slug"]]
                profile = self._profile(conn, brand, spec, voices)
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
            "brands": {key: {"id": str(row["id"]), "name": row["display_name"], "facebook_url": row["metadata"].get("facebook_url")} for key, row in brands.items()},
            "profiles": {key: {"id": str(row["id"]), "version": row["version"]} for key, row in profiles.items()},
            "plans": {key: {"id": str(row["id"]), "month_start": str(row["month_start"])} for key, row in plans.items()},
            "sample_content": {key: {"id": str(row["id"]), "title": row["title"]} for key, row in samples.items()},
            "voices": {
                key: {"id": str(row["id"]), "voice": row["provider_voice_id"], "model": self.voice_model}
                for key, row in voices.items()
            },
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
            metadata = {
                "local_onboarding": True,
                "cadence": f"{spec['target']} masters monthly",
                "facebook_url": spec["facebook_url"],
                "p110_four_brand": True,
            }
            row = conn.execute(
                """INSERT INTO football_brief.brands
                   (slug,display_name,niche,primary_platform,content_mode,monthly_target,
                    source_links,content_pillars,active,metadata)
                   VALUES (%s,%s,%s,'facebook','video',%s,%s::jsonb,%s::jsonb,true,%s::jsonb)
                   ON CONFLICT (slug) DO UPDATE SET
                     display_name=EXCLUDED.display_name,niche=EXCLUDED.niche,
                     primary_platform='facebook',content_mode='video',
                     monthly_target=EXCLUDED.monthly_target,source_links=EXCLUDED.source_links,
                     content_pillars=EXCLUDED.content_pillars,active=true,
                     metadata=football_brief.brands.metadata || EXCLUDED.metadata
                   RETURNING *""",
                (
                    spec["slug"], spec["display_name"], spec["niche"], spec["target"],
                    json.dumps([spec["facebook_url"]]),
                    json.dumps(spec["pillars"]),
                    json.dumps(metadata),
                ),
            ).fetchone()
            output[spec["slug"]] = dict(row)
        return output

    def _voices(self, conn: Any) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for spec in self.voice_specs:
            row = conn.execute(
                """INSERT INTO football_brief.approved_voices
                   (provider,provider_voice_id,display_name,voice_type,approval_status,
                    allowed_languages,allowed_platforms,prohibited_uses,approved_by,approved_at,metadata)
                   VALUES ('kokoro',%s,%s,'premade','approved',
                           ARRAY['en','en-US']::text[],%s::text[],
                           ARRAY['impersonation','deceptive_synthetic_media']::text[],
                           %s,now(),%s::jsonb)
                   ON CONFLICT (provider,provider_voice_id) DO UPDATE SET
                     display_name=EXCLUDED.display_name,approval_status='approved',
                     allowed_languages=EXCLUDED.allowed_languages,allowed_platforms=EXCLUDED.allowed_platforms,
                     approved_by=EXCLUDED.approved_by,approved_at=now(),
                     metadata=football_brief.approved_voices.metadata || EXCLUDED.metadata
                   RETURNING *""",
                (
                    spec["voice"],
                    f"Kokoro {spec['voice']} — {spec['display_name']}",
                    PLATFORMS,
                    self.admin_id,
                    json.dumps({
                        "model_id": self.voice_model,
                        "local_only": True,
                        "commercial_review_required": True,
                        "p110_fixed_preset": spec["key"],
                    }),
                ),
            ).fetchone()
            output[spec["key"]] = dict(row)
        return output

    def _profile(
        self,
        conn: Any,
        brand: dict[str, Any],
        spec: dict[str, Any],
        voices: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        active = conn.execute(
            "SELECT * FROM football_brief.brand_profiles WHERE brand_id=%s AND status='active'",
            (brand["id"],),
        ).fetchone()
        if active:
            readiness = conn.execute(
                """SELECT count(*) FILTER (WHERE p.active)::int AS active_count,
                          count(*) FILTER (WHERE p.active AND p.is_default)::int AS default_count,
                          bool_and(p.approved_voice_id IS NOT NULL) AS voices_ready
                   FROM football_brief.brand_narration_presets p
                   WHERE p.brand_profile_id=%s""",
                (active["id"],),
            ).fetchone()
            platform_set = set(active["platforms"] or [])
            if (
                int(readiness["active_count"] or 0) == 3
                and int(readiness["default_count"] or 0) == 1
                and bool(readiness["voices_ready"])
                and set(PLATFORMS).issubset(platform_set)
            ):
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
            audience = dict(active["audience"] or {}) if active else {"primary": "English-speaking factual video audiences"}
            visual_rules = dict(active["visual_rules"] or {}) if active else {}
            restrictions = dict(active["content_restrictions"] or {}) if active else {}
            cadence = dict(active["cadence"] or {}) if active else {}
            budget = dict(active["budget"] or {}) if active else {}
            visual_rules.update({
                "aspect_ratios": ["16:9", "4:5", "9:16"],
                "original_assets_only": True,
                "keyframe_provider": "comfyui-sdxl-local",
                "master_first": True,
            })
            restrictions.update({
                "factual_claims_need_sources": True,
                "human_approval_required": True,
                "no_fabricated_citations": True,
            })
            cadence.update({"monthly_target": spec["target"]})
            budget.update({"local_generation_default": True, "managed_monthly_limit_usd": 0})
            draft = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id,version,status,default_language,audience,tone,visual_rules,
                    content_restrictions,cadence,platforms,budget,created_by)
                   VALUES (%s,%s,'draft',%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::text[],%s::jsonb,%s)
                   RETURNING *""",
                (
                    brand["id"],
                    version,
                    active["default_language"] if active else "en-US",
                    json.dumps(audience),
                    spec["tone"],
                    json.dumps(visual_rules),
                    json.dumps(restrictions),
                    json.dumps(cadence),
                    PLATFORMS,
                    json.dumps(budget),
                    self.admin_id,
                ),
            ).fetchone()
        else:
            conn.execute(
                """UPDATE football_brief.brand_profiles
                   SET default_language='en-US',tone=%s,
                       audience=audience || %s::jsonb,
                       visual_rules=visual_rules || %s::jsonb,
                       content_restrictions=content_restrictions || %s::jsonb,
                       cadence=cadence || %s::jsonb,
                       platforms=%s::text[],
                       budget=budget || %s::jsonb
                   WHERE id=%s AND status='draft'""",
                (
                    spec["tone"],
                    json.dumps({"primary": "English-speaking factual video audiences"}),
                    json.dumps({"aspect_ratios": ["16:9", "4:5", "9:16"], "original_assets_only": True, "master_first": True}),
                    json.dumps({"factual_claims_need_sources": True, "human_approval_required": True, "no_fabricated_citations": True}),
                    json.dumps({"monthly_target": spec["target"]}),
                    PLATFORMS,
                    json.dumps({"local_generation_default": True, "managed_monthly_limit_usd": 0}),
                    draft["id"],
                ),
            )
            draft = conn.execute("SELECT * FROM football_brief.brand_profiles WHERE id=%s", (draft["id"],)).fetchone()

        conn.execute(
            "DELETE FROM football_brief.brand_narration_presets WHERE brand_profile_id=%s",
            (draft["id"],),
        )
        for voice_spec in self.voice_specs:
            conn.execute(
                """INSERT INTO football_brief.brand_narration_presets
                   (brand_profile_id,preset_key,display_name,role,approved_voice_id,language,
                    speed,style,pronunciation_rules,format_filters,topic_filters,is_default,active)
                   VALUES (%s,%s,%s,%s,%s,'en-US',%s,%s::jsonb,'{}'::jsonb,
                           %s::text[],ARRAY[]::text[],%s,true)""",
                (
                    draft["id"],
                    voice_spec["key"],
                    voice_spec["display_name"],
                    voice_spec["role"],
                    voices[voice_spec["key"]]["id"],
                    voice_spec["speed"],
                    json.dumps({**voice_spec["style"], "brand_slug": spec["slug"]}),
                    FORMATS,
                    voice_spec["is_default"],
                ),
            )

        if active:
            conn.execute(
                "UPDATE football_brief.brand_profiles SET status='retired' WHERE id=%s AND status='active'",
                (active["id"],),
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
                json.dumps({
                    "local_first": True,
                    "human_review": True,
                    "managed_renderer": "not_configured",
                    "master_duration_range_seconds": [10, 150],
                    "platform_all_supported": True,
                }),
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
            return dict(existing)
        fingerprint = hashlib.sha256(f"local-smoke:{spec['slug']}:v2".encode()).hexdigest()
        return dict(conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id,scheduled_for,title,concept,format,stage,concept_fingerprint,semantic_key,
                version,brand_profile_id,narration_preset_id,metadata)
               VALUES (%s,%s,%s,%s,'vertical_short','idea',%s,%s,1,%s,%s,%s::jsonb)
               RETURNING *""",
            (
                plan["id"], self.plan_month, f"Local production smoke — {spec['display_name']}",
                f"Create an original 45-second {spec['display_name']} explainer with web-reviewed sources, local narration, and reviewable keyframes.",
                fingerprint, semantic, profile["id"], preset["id"],
                json.dumps({
                    "local_smoke_fixture": True,
                    "automatic_approval": False,
                    "automatic_publication": False,
                    "facebook_url": spec["facebook_url"],
                }),
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
