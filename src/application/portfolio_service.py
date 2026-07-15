"""Database-backed multi-brand planning, review, duplicate, packaging, and learning service."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


STAGE_GATE = {
    "idea": ("idea", "script"),
    "script": ("script", "preview"),
    "preview": ("preview", "premium"),
    "premium": ("premium_spend", "package"),
    "package": ("package", "ready"),
    "ready": ("publish", "published"),
}


def canonical_concept(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return " ".join(words)


def concept_fingerprint(*, brand_slug: str, concept: str, format_name: str) -> str:
    payload = {"brand": brand_slug, "concept": canonical_concept(concept), "format": format_name.lower().strip()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def semantic_key(concept: str) -> str:
    stop = {"a", "an", "and", "are", "how", "in", "is", "of", "the", "to", "what", "why"}
    tokens = sorted({word for word in canonical_concept(concept).split() if word not in stop})
    return "-".join(tokens[:12]) or "untitled"


def paid_render_route(scene: dict[str, Any]) -> dict[str, Any]:
    realism = bool(scene.get("realism_critical"))
    hero = bool(scene.get("hero_shot"))
    factual_graphic = bool(scene.get("factual_graphic"))
    if factual_graphic and not realism:
        return {"tier": "deterministic", "paid": False, "reason": "controlled factual motion is clearer and cheaper"}
    if realism or hero:
        return {"tier": "premium", "paid": True, "reason": "realism or hook quality materially affects trust and retention"}
    return {"tier": "open_source_preview", "paid": False, "reason": "validate timing and motion before escalation"}


def platform_package_defaults(*, title: str, caption: str, hashtags: list[str]) -> list[dict[str, Any]]:
    clean_tags = list(dict.fromkeys(tag.strip().lstrip("#") for tag in hashtags if tag.strip()))[:8]
    return [
        {"platform": "facebook", "title": title, "caption": caption, "hashtags": clean_tags[:5], "priority": 1, "watermark_free": True},
        {"platform": "youtube_shorts", "title": title[:100], "caption": caption, "hashtags": clean_tags[:3], "priority": 2, "watermark_free": True},
        {"platform": "tiktok", "title": title, "caption": caption, "hashtags": clean_tags[:5], "priority": 3, "watermark_free": True},
    ]


def analytics_recommendation(metrics: dict[str, Any]) -> dict[str, str]:
    retention = float(metrics.get("average_view_percentage") or 0)
    hook = float(metrics.get("three_second_view_rate") or 0)
    shares = int(metrics.get("shares") or 0)
    views = max(int(metrics.get("views") or 0), 1)
    share_rate = shares / views
    if hook < 45:
        return {"action": "rewrite_hook", "reason": "weak first-three-second hold", "cadence": "hold"}
    if retention < 55:
        return {"action": "tighten_middle", "reason": "hook works but completion quality is weak", "cadence": "hold"}
    if share_rate >= 0.01:
        return {"action": "expand_pillar", "reason": "strong share signal", "cadence": "increase_selectively"}
    return {"action": "continue_test", "reason": "insufficient decisive signal", "cadence": "hold"}


class PortfolioService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def create_brand(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.brands
                   (slug, display_name, niche, primary_platform, content_mode, monthly_target, source_links, content_pillars, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                   ON CONFLICT (slug) DO UPDATE SET display_name=EXCLUDED.display_name, niche=EXCLUDED.niche,
                     primary_platform=EXCLUDED.primary_platform, content_mode=EXCLUDED.content_mode,
                     monthly_target=EXCLUDED.monthly_target, source_links=EXCLUDED.source_links,
                     content_pillars=EXCLUDED.content_pillars, metadata=EXCLUDED.metadata
                   RETURNING *""",
                (payload["slug"], payload["display_name"], payload["niche"], payload.get("primary_platform", "facebook"),
                 payload["content_mode"], payload["monthly_target"], json.dumps(payload.get("source_links", [])),
                 json.dumps(payload.get("content_pillars", [])), json.dumps(payload.get("metadata", {}))),
            ).fetchone()
        return dict(row)

    def list_brands(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        where = "WHERE active = true" if active_only else ""
        with self.database.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM football_brief.brands {where} ORDER BY display_name"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_month_plan(self, *, brand_id: UUID, month_start: date, target_count: int, strategy: dict[str, Any], created_by: str) -> dict[str, Any]:
        if month_start.day != 1:
            return {"ok": False, "error": "month_start_must_be_first_day"}
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.monthly_content_plans
                   (brand_id, month_start, target_count, strategy, created_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (brand_id, month_start) DO UPDATE SET
                     target_count=EXCLUDED.target_count, strategy=EXCLUDED.strategy
                   RETURNING *""",
                (brand_id, month_start, target_count, json.dumps(strategy), created_by),
            ).fetchone()
        return {"ok": True, "plan": dict(row)}

    def queue(self, *, brand_id: UUID | None = None, stage: str | None = None) -> list[dict[str, Any]]:
        conditions, values = ["b.active = true"], []
        if brand_id:
            conditions.append("b.id = %s"); values.append(brand_id)
        if stage:
            conditions.append("pc.stage = %s"); values.append(stage)
        sql = f"""SELECT pc.*, b.id AS brand_id, b.slug AS brand_slug, b.display_name AS brand_name, mp.month_start
                  FROM football_brief.portfolio_content pc
                  JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                  JOIN football_brief.brands b ON b.id=mp.brand_id
                  WHERE {' AND '.join(conditions)} ORDER BY pc.scheduled_for, b.display_name"""
        with self.database.connection() as conn:
            return [dict(row) for row in conn.execute(sql, tuple(values)).fetchall()]

    def add_content(self, *, plan_id: UUID, brand_slug: str, scheduled_for: date, title: str, concept: str, format_name: str) -> dict[str, Any]:
        fingerprint = concept_fingerprint(brand_slug=brand_slug, concept=concept, format_name=format_name)
        key = semantic_key(concept)
        with self.database.transaction() as conn:
            duplicate = conn.execute(
                "SELECT id, title, stage FROM football_brief.portfolio_content WHERE concept_fingerprint=%s OR semantic_key=%s LIMIT 1",
                (fingerprint, key),
            ).fetchone()
            if duplicate:
                return {"ok": False, "duplicate": True, "match": dict(duplicate), "fingerprint": fingerprint}
            row = conn.execute(
                """INSERT INTO football_brief.portfolio_content
                   (plan_id, scheduled_for, title, concept, format, concept_fingerprint, semantic_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (plan_id, scheduled_for, title, concept, format_name, fingerprint, key),
            ).fetchone()
        return {"ok": True, "duplicate": False, "item": dict(row)}

    def approve_gate(self, *, content_id: UUID, gate: str, reviewer: str, rationale: str, decision: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            item = conn.execute("SELECT * FROM football_brief.portfolio_content WHERE id=%s FOR UPDATE", (content_id,)).fetchone()
            if not item:
                return {"ok": False, "error": "content_not_found"}
            expected = STAGE_GATE.get(item["stage"])
            if not expected or expected[0] != gate:
                return {"ok": False, "error": "gate_stage_mismatch", "stage": item["stage"], "expected_gate": expected[0] if expected else None}
            conn.execute(
                """INSERT INTO football_brief.portfolio_approvals
                   (portfolio_content_id, gate, decision, reviewer, rationale, content_version)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (content_id, gate, decision, reviewer, rationale, item["version"]),
            )
            next_stage = expected[1] if decision == "approved" else ("blocked" if decision == "rejected" else item["stage"])
            conn.execute("UPDATE football_brief.portfolio_content SET stage=%s WHERE id=%s", (next_stage, content_id))
        return {"ok": True, "previous_stage": item["stage"], "stage": next_stage, "decision": decision}

    def create_platform_packages(self, *, content_id: UUID, title: str, caption: str, hashtags: list[str], disclosure: dict[str, Any] | None = None) -> dict[str, Any]:
        defaults = platform_package_defaults(title=title, caption=caption, hashtags=hashtags)
        created: list[dict[str, Any]] = []
        with self.database.transaction() as conn:
            item = conn.execute("SELECT stage FROM football_brief.portfolio_content WHERE id=%s", (content_id,)).fetchone()
            if not item:
                return {"ok": False, "error": "content_not_found"}
            if item["stage"] not in {"package", "ready"}:
                return {"ok": False, "error": "package_gate_not_reached", "stage": item["stage"]}
            for package in defaults:
                row = conn.execute(
                    """INSERT INTO football_brief.platform_packages
                       (portfolio_content_id, platform, title, caption, hashtags, disclosure, package_manifest)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                       ON CONFLICT (portfolio_content_id, platform, version) DO UPDATE SET
                         title=EXCLUDED.title, caption=EXCLUDED.caption, hashtags=EXCLUDED.hashtags,
                         disclosure=EXCLUDED.disclosure, package_manifest=EXCLUDED.package_manifest
                       RETURNING *""",
                    (content_id, package["platform"], package["title"], package["caption"],
                     json.dumps(package["hashtags"]), json.dumps(disclosure or {}), json.dumps(package)),
                ).fetchone()
                created.append(dict(row))
        return {"ok": True, "count": len(created), "packages": created}

    def record_metrics(self, *, package_id: UUID, observed_at: Any, metrics: dict[str, Any], source: str = "manual") -> dict[str, Any]:
        fields = ("views", "watch_seconds", "average_view_percentage", "three_second_view_rate", "engagements", "shares", "followers_gained", "revenue_usd")
        values = [metrics.get(field) for field in fields]
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.performance_observations
                   (platform_package_id, observed_at, views, watch_seconds, average_view_percentage,
                    three_second_view_rate, engagements, shares, followers_gained, revenue_usd, source, raw_metrics)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT (platform_package_id, observed_at) DO NOTHING RETURNING *""",
                (package_id, observed_at, *values, source, json.dumps(metrics)),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "observation_already_recorded"}
        return {"ok": True, "observation": dict(row), "recommendation": analytics_recommendation(metrics)}
