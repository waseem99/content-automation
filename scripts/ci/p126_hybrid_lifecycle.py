from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from src.application.assets.hashing import inspect_file
from src.application.campaigns.models import (
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.hybrid_routing import HybridRoutingService, PAID_ROUTE_CLASSES
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _scene(detail: dict, sequence: int) -> dict:
    return next(row for row in detail["scenes"] if int(row["sequence"]) == sequence)


def _candidate(scene: dict, route_class: str) -> dict:
    return next(row for row in scene["candidates"] if row["route_class"] == route_class and row["eligible"])


def _selected(scene: dict) -> dict:
    return next(row for row in scene["candidates"] if row["id"] == scene["selected_candidate_id"])


def _complete_selected(
    service: HybridRoutingService,
    *,
    scene: dict,
    billing_key: str,
    actor: str,
    accepted_seconds: float,
) -> dict:
    selected = _selected(scene)
    created = service.create_attempt(
        scene_id=UUID(str(scene["id"])),
        candidate_id=UUID(str(selected["id"])),
        billing_key=billing_key,
        actor=actor,
    )
    return service.complete_attempt(
        attempt_id=UUID(str(created["attempt"]["id"])),
        status="accepted",
        rendered_seconds=accepted_seconds,
        accepted_seconds=accepted_seconds,
        actual_cost=Decimal("0"),
        actor=actor,
        evidence={"synthetic_ci": True},
    )


def run() -> None:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        with database.connection() as conn:
            context = conn.execute(
                """SELECT brand.id AS brand_id,brand.primary_platform,content.id AS content_id,
                          COALESCE(content.content_family_id,content.id) AS content_family_id
                   FROM football_brief.brands brand
                   JOIN football_brief.monthly_content_plans plan ON plan.brand_id=brand.id
                   JOIN football_brief.portfolio_content content ON content.plan_id=plan.id
                   WHERE brand.active=true
                   ORDER BY brand.slug,content.created_at
                   LIMIT 1"""
            ).fetchone()
            jobs_before = int(
                conn.execute("SELECT count(*)::int AS value FROM football_brief.generation_jobs").fetchone()["value"]
            )
        assert context
        actor = "local-admin"
        campaign_service = ValidatedCampaignService(database)
        created = campaign_service.create_campaign(
            CampaignCreateRequest(
                campaign_key="p126-ci-hybrid-routing",
                brand_id=UUID(str(context["brand_id"])),
                name="P126 Hybrid Routing Lifecycle",
            ),
            actor=actor,
        )
        campaign_id = UUID(str(created["campaign"]["id"]))
        version_id = UUID(str(created["versions"][0]["id"]))
        primary = str(context["primary_platform"])
        campaign_service.add_items(
            campaign_version_id=version_id,
            request=CampaignItemsAddRequest(
                items=[
                    CampaignItemInput(
                        item_key="hybrid-master",
                        title="Exact 120 second hybrid routing master",
                        topic="Prove package-native route planning without provider submission.",
                        primary_platform=primary,
                        target_platforms=[primary],
                        target_duration_seconds=120,
                        short_cut_count=2,
                        scheduled_for=date(2026, 8, 2),
                    )
                ]
            ),
            actor=actor,
        )
        assert campaign_service.validate_version(
            campaign_version_id=version_id,
            actor=actor,
        )["ok"] is True
        campaign_service.activate_version(
            campaign_version_id=version_id,
            actor=actor,
        )
        with database.transaction() as conn:
            item = conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='ready_for_final_video_generation',
                       disposition='ready_for_final_video_generation',
                       portfolio_content_id=%s,content_family_id=%s,ready_at=now(),updated_at=now()
                   WHERE campaign_version_id=%s AND item_key='hybrid-master'
                   RETURNING *""",
                (context["content_id"], context["content_family_id"], version_id),
            ).fetchone()
        package = {
            "schema": "ready-for-final-video-generation/v1",
            "campaign": {
                "id": str(campaign_id),
                "version_id": str(version_id),
                "item_id": str(item["id"]),
                "item_key": "hybrid-master",
            },
            "brand": {"id": str(context["brand_id"]), "name": "P126 CI Brand"},
            "content_family": {
                "master_content_id": str(context["content_id"]),
                "content_family_id": str(context["content_family_id"]),
                "primary_platform": primary,
                "target_platforms": [primary],
                "target_duration_seconds": 120,
                "short_cut_count": 2,
            },
            "scene_plan": {
                "exact_target_duration_seconds": 120,
                "timeline_corrected": False,
                "shots": [
                    {
                        "shot_id": f"S{index:03d}",
                        "scene_key": f"scene-{index}",
                        "start_seconds": (index - 1) * 30,
                        "end_seconds": index * 30,
                        "duration_seconds": 30,
                        "narration_text": f"Narration segment {index}.",
                        "prompt": (
                            "Use the approved reusable opening treatment with restrained motion."
                            if index == 1
                            else "Create a controlled factual sequence with subtle natural motion."
                        ),
                        "negative_prompt": "No generated text; no logos; no abrupt cuts.",
                        "continuity_bindings": {
                            "content_family_id": str(context["content_family_id"]),
                            "persistent_subjects": {"subject": "p126-ci-subject"},
                        },
                        "minimum_take_count": 1,
                        "preferred_take_count": 2 if index in {1, 2, 4} else 1,
                        "renderer_route": "unassigned_hybrid_router",
                    }
                    for index in range(1, 5)
                ],
            },
            "narration_plan": {
                "segments": [
                    {
                        "segment_id": f"scene-{index}",
                        "start_seconds": (index - 1) * 30,
                        "end_seconds": index * 30,
                        "duration_seconds": 30,
                        "text": f"Narration segment {index}.",
                    }
                    for index in range(1, 5)
                ],
                "generated_audio": False,
            },
            "caption_package": {"outputs": [], "published": False},
            "routing_constraints": {
                "storage_providers": ["local", "google_drive"],
                "automatic_paid_spend": False,
                "automatic_public_publishing": False,
                "final_video_generation_deferred": True,
            },
        }
        with database.transaction() as conn:
            package_row = conn.execute(
                """INSERT INTO football_brief.pre_generation_packages
                   (campaign_item_id,version,status,package_sha256,package,created_by)
                   VALUES (%s,1,'ready',%s,%s::jsonb,%s) RETURNING *""",
                (item["id"], _sha(package), _json(package), actor),
            ).fetchone()

        artifact = Path(".runtime/artifacts/p126-reusable-opening.txt")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("approved reusable opening template\n", encoding="utf-8")
        inspected = inspect_file(artifact.resolve())
        with database.transaction() as conn:
            asset = conn.execute(
                """INSERT INTO football_brief.assets
                   (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                    sha256,mime_type,size_bytes,created_by)
                   VALUES ('document','owned','approved',%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (
                    artifact.name,
                    artifact.resolve().as_uri(),
                    inspected.sha256,
                    inspected.mime_type,
                    inspected.size_bytes,
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.asset_storage_locations
                   (asset_id,provider,locator,status,sha256,size_bytes,verified_at,created_by)
                   VALUES (%s,'local',%s,'available',%s,%s,now(),%s)""",
                (asset["id"], str(artifact.resolve()), inspected.sha256, inspected.size_bytes, actor),
            )

        routing = HybridRoutingService(database)
        template = routing.register_template(
            template_key="p126-ci-opening",
            category="reusable_asset",
            specification={"shot_ids": ["S001"]},
            actor=actor,
            brand_id=UUID(str(context["brand_id"])),
            asset_id=UUID(str(asset["id"])),
            duration_seconds=30,
            quality_rating=95,
            activate=True,
        )
        assert template["template"]["status"] == "active"

        detail = routing.plan_package(
            package_id=UUID(str(package_row["id"])),
            actor=actor,
        )
        plan_id = UUID(str(detail["plan"]["id"]))
        assert detail["plan"]["status"] == "ready"
        assert detail["plan"]["exact_duration_seconds"] == 120.0
        assert detail["plan"]["estimated_cost"] == 0.0
        assert len(detail["scenes"]) == 4
        assert all(scene["selected_candidate_id"] for scene in detail["scenes"])
        assert all(len(scene["fallback_chain"]) >= 2 for scene in detail["scenes"])
        assert _selected(_scene(detail, 1))["route_class"] == "reuse_asset"
        assert all(
            _selected(_scene(detail, sequence))["route_class"] == "deterministic_composition"
            for sequence in (2, 3, 4)
        )
        planned = detail["plan"]["route_seconds"]
        assert planned["reuse_asset"] == 30.0
        assert planned["deterministic_composition"] == 90.0
        assert sum(float(planned[route]) for route in PAID_ROUTE_CLASSES) == 0.0
        assert detail["spend_approval"] is None
        assert detail["attempts"] == []

        scene_three = _scene(detail, 3)
        manual_three = _candidate(scene_three, "manual_edit")
        detail = routing.override_scene(
            scene_id=UUID(str(scene_three["id"])),
            candidate_id=UUID(str(manual_three["id"])),
            rationale="Use a manual editorial treatment to prove the audited override path.",
            actor="local-reviewer",
        )
        assert _selected(_scene(detail, 3))["route_class"] == "manual_edit"

        _complete_selected(
            routing,
            scene=_scene(detail, 1),
            billing_key="p126-ci-s001-reuse",
            actor=actor,
            accepted_seconds=30,
        )

        detail = routing.detail(plan_id=plan_id)
        scene_two = _scene(detail, 2)
        deterministic_two = _selected(scene_two)
        first_two = routing.create_attempt(
            scene_id=UUID(str(scene_two["id"])),
            candidate_id=UUID(str(deterministic_two["id"])),
            billing_key="p126-ci-s002-first",
            actor=actor,
        )
        replay_two = routing.create_attempt(
            scene_id=UUID(str(scene_two["id"])),
            candidate_id=UUID(str(deterministic_two["id"])),
            billing_key="p126-ci-s002-first",
            actor=actor,
        )
        assert replay_two["idempotent"] is True
        assert replay_two["attempt"]["id"] == first_two["attempt"]["id"]
        failed_two = routing.complete_attempt(
            attempt_id=UUID(str(first_two["attempt"]["id"])),
            status="failed",
            rendered_seconds=30,
            accepted_seconds=0,
            actual_cost=Decimal("0"),
            failure_code="synthetic_quality_miss",
            actor=actor,
            evidence={"synthetic_ci": True},
        )
        assert failed_two["next_candidate"]["route_class"] == "manual_edit"

        detail = routing.detail(plan_id=plan_id)
        _complete_selected(
            routing,
            scene=_scene(detail, 2),
            billing_key="p126-ci-s002-fallback",
            actor=actor,
            accepted_seconds=30,
        )
        detail = routing.detail(plan_id=plan_id)
        _complete_selected(
            routing,
            scene=_scene(detail, 3),
            billing_key="p126-ci-s003-manual",
            actor=actor,
            accepted_seconds=30,
        )
        detail = routing.detail(plan_id=plan_id)
        _complete_selected(
            routing,
            scene=_scene(detail, 4),
            billing_key="p126-ci-s004-deterministic",
            actor=actor,
            accepted_seconds=30,
        )

        final = routing.detail(plan_id=plan_id)
        assert final["plan"]["status"] == "completed"
        assert len(final["attempts"]) == 5
        assert final["spend_approval"] is None
        report = routing.report(plan_id=plan_id)
        assert report["finished_seconds"] == 120.0
        assert report["generated_seconds"] == 0.0
        assert report["retry_seconds"] == 30.0
        assert report["deterministic_reused_seconds"] == 60.0
        assert report["manual_edit_seconds"] == 60.0
        assert report["accepted_cloud_seconds"] == 0.0
        assert report["accepted_premium_seconds"] == 0.0
        assert report["actual_cost"] == 0.0
        assert report["automatic_paid_execution"] is False
        assert report["public_publishing"] is False

        with database.connection() as conn:
            jobs_after = int(
                conn.execute("SELECT count(*)::int AS value FROM football_brief.generation_jobs").fetchone()["value"]
            )
            paid_attempts = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.hybrid_route_attempts attempt
                       JOIN football_brief.hybrid_route_candidates candidate ON candidate.id=attempt.candidate_id
                       JOIN football_brief.hybrid_route_scenes scene ON scene.id=attempt.route_scene_id
                       WHERE scene.route_plan_id=%s AND candidate.route_class=ANY(%s::text[])""",
                    (plan_id, list(PAID_ROUTE_CLASSES)),
                ).fetchone()["value"]
            )
            overrides = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.hybrid_route_overrides override_row
                       JOIN football_brief.hybrid_route_scenes scene ON scene.id=override_row.route_scene_id
                       WHERE scene.route_plan_id=%s""",
                    (plan_id,),
                ).fetchone()["value"]
            )
        assert jobs_after == jobs_before
        assert paid_attempts == 0
        assert overrides == 1
    finally:
        database.close()


if __name__ == "__main__":
    run()
