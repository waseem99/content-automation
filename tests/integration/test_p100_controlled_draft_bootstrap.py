from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from src.application.scripts.models import (
    ClaimSourceDraft,
    ClaimSupportType,
    ScriptDecision,
    ScriptGenerateRequest,
    SourceDraft,
    SourceRightsDeclaration,
    SourceSupportUpdateRequest,
    SourceType,
)
from src.application.scripts.service import ScriptReviewService
from src.operations.settings import OperationsSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def bootstrap_client(database) -> TestClient:
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": "admin.one",
            "producer-key": "producer.one",
        },
        resolve_identities_from_database=True,
    )
    app = create_configured_app(
        database=database,
        auth_settings=auth,
        runtime_settings=OperatorRuntimeSettings(
            _env_file=None,
            database_require_schema=False,
        ),
        operations_settings=OperationsSettings(
            _env_file=None,
            environment="staging",
            release_key="p100-controlled-bootstrap-test",
            git_sha="1" * 40,
            image_digest="sha256:" + "2" * 64,
            configuration_digest="3" * 64,
            migration_head="0089_acceptance_runbook_drill.sql",
            requests_per_minute=1000,
            storage_capacity_bytes=1024 * 1024,
        ),
    )
    return TestClient(app)


def script_request(seed: int) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        platform="youtube_shorts",
        format="vertical_short",
        language="en-US",
        target_duration_seconds=60,
        words_per_minute=150,
        duration_tolerance_percent=10,
        seed=seed,
    )


def source_request(*, expected_lock: int, suffix: str) -> SourceSupportUpdateRequest:
    digest_character = "a" if suffix.startswith("animal-x") else "b"
    source = SourceDraft(
        source_key="source-primary",
        source_type=SourceType.ACADEMIC,
        title=f"Reviewed evidence for controlled pilot {suffix}",
        publisher="Controlled Pilot Evidence Journal",
        canonical_url=f"https://example.org/p100/{suffix}",
        quality_score=95,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and paraphrased educational explanation",
        evidence_digest=digest_character * 64,
        notes="No source wording or media is copied into the output.",
    )
    return SourceSupportUpdateRequest(
        expected_lock_version=expected_lock,
        sources=[source],
        claim_sources=[
            ClaimSourceDraft(
                claim_key="claim-hook",
                source_key=source.source_key,
                support_type=ClaimSupportType.CORROBORATING,
                locator="Abstract and findings",
                support_note="Corroborates the factual opening.",
            ),
            ClaimSourceDraft(
                claim_key="claim-body",
                source_key=source.source_key,
                support_type=ClaimSupportType.DIRECT,
                locator="Methods and findings",
                support_note="Directly supports the central mechanism.",
            ),
        ],
        supported_claim_keys=["claim-hook", "claim-body"],
    )


def seed_selectable_contents(database, seeded) -> dict[str, object]:
    with database.transaction() as conn:
        publisher = conn.execute(
            """INSERT INTO football_brief.operator_users
               (operator_id,display_name,created_by)
               VALUES ('publisher.bootstrap','Bootstrap Publisher','admin.one')
               RETURNING id"""
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.operator_user_roles
               (operator_user_id,role,assigned_by)
               VALUES (%s,'publisher','admin.one')""",
            (publisher["id"],),
        )
        producer = conn.execute(
            "SELECT id FROM football_brief.operator_users WHERE operator_id='producer.one'"
        ).fetchone()
        reviewer = conn.execute(
            "SELECT id FROM football_brief.operator_users WHERE operator_id='reviewer.one'"
        ).fetchone()
        voice = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider,provider_voice_id,display_name,voice_type,approval_status,
                allowed_languages,allowed_platforms,approved_by,approved_at)
               VALUES ('kokoro-onnx','bootstrap_voice','Bootstrap Voice','premade','approved',
                       ARRAY['en'],ARRAY['youtube_shorts'],'admin.one',now())
               RETURNING id"""
        ).fetchone()

        result: dict[str, object] = {"brands": {}, "contents": {}}
        for brand_index, (slug, name, marker) in enumerate(
            (
                ("animal-x", "Animal X", "a"),
                ("rawr-nation", "Rawr Nation", "b"),
            ),
            start=1,
        ):
            brand = conn.execute(
                """INSERT INTO football_brief.brands
                   (slug,display_name,niche,primary_platform,content_mode,monthly_target,
                    content_pillars)
                   VALUES (%s,%s,'Original animal education','youtube_shorts','video',20,
                           '["education","mechanism"]'::jsonb)
                   RETURNING id""",
                (slug, name),
            ).fetchone()
            for operator_id in (producer["id"], reviewer["id"], publisher["id"]):
                conn.execute(
                    """INSERT INTO football_brief.operator_brand_assignments
                       (operator_user_id,brand_id,assigned_by)
                       VALUES (%s,%s,'admin.one')""",
                    (operator_id, brand["id"]),
                )
            profile = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id,version,default_language,audience,tone,visual_rules,
                    content_restrictions,cadence,platforms,budget,created_by)
                   VALUES (%s,1,'en-US','{"age":"18-34"}'::jsonb,
                           'clear factual narration','{"pace":"controlled"}'::jsonb,
                           '{"avoid":["copied footage"]}'::jsonb,'{"weekly":2}'::jsonb,
                           ARRAY['youtube_shorts'],'{"monthly_local_usd":0}'::jsonb,'admin.one')
                   RETURNING id""",
                (brand["id"],),
            ).fetchone()
            preset = conn.execute(
                """INSERT INTO football_brief.brand_narration_presets
                   (brand_profile_id,preset_key,display_name,role,approved_voice_id,
                    language,is_default)
                   VALUES (%s,'primary','Primary','primary',%s,'en-US',true)
                   RETURNING id""",
                (profile["id"], voice["id"]),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.brand_profiles
                   SET status='active',activated_by='admin.one',activated_at=now()
                   WHERE id=%s""",
                (profile["id"],),
            )
            plan = conn.execute(
                """INSERT INTO football_brief.monthly_content_plans
                   (brand_id,month_start,target_count,status,created_by)
                   VALUES (%s,DATE '2026-12-01',2,'draft','admin.one')
                   RETURNING id""",
                (brand["id"],),
            ).fetchone()
            batch = conn.execute(
                """INSERT INTO football_brief.concept_generation_batches
                   (brand_id,brand_profile_id,month_start,requested_count,seed,status,
                    candidate_count,created_by,completed_at)
                   VALUES (%s,%s,DATE '2026-12-01',2,%s,'ready_for_review',2,'admin.one',now())
                   RETURNING id""",
                (brand["id"], profile["id"], 100 + brand_index),
            ).fetchone()

            brand_contents = []
            for ordinal in (1, 2):
                content = conn.execute(
                    """INSERT INTO football_brief.portfolio_content
                       (plan_id,scheduled_for,title,concept,format,concept_fingerprint,
                        semantic_key,brand_profile_id,narration_preset_id)
                       VALUES (%s,DATE '2026-12-01' + %s,%s,%s,'vertical_short',%s,%s,%s,%s)
                       RETURNING id,version""",
                    (
                        plan["id"],
                        ordinal,
                        f"{name} controlled pilot {ordinal}",
                        f"Explain an original {name} mechanism for controlled pilot item {ordinal}.",
                        (marker + str(ordinal)) * 32,
                        f"p100-bootstrap-{slug}-{ordinal}",
                        profile["id"],
                        preset["id"],
                    ),
                ).fetchone()
                workflow_id = uuid4()
                workflow_version_id = uuid4()
                conn.execute(
                    """INSERT INTO football_brief.production_workflows
                       (id,portfolio_content_id,current_stage,status,current_version_id,
                        lock_version,created_by)
                       VALUES (%s,%s,'script_draft','active',%s,1,'admin.one')""",
                    (workflow_id, content["id"], workflow_version_id),
                )
                conn.execute(
                    """INSERT INTO football_brief.production_workflow_versions
                       (id,workflow_id,version,basis_content_version,status,snapshot,
                        created_by,last_edited_by)
                       VALUES (%s,%s,1,%s,'working','{}'::jsonb,'admin.one','admin.one')""",
                    (workflow_version_id, workflow_id, content["version"]),
                )
                conn.execute(
                    """INSERT INTO football_brief.concept_candidates
                       (batch_id,ordinal,status,title,hook,concept,format,pillar,rationale,
                        factual_risk,production_complexity,estimated_cost_usd,
                        recommended_route,concept_fingerprint,semantic_key,semantic_tokens,
                        originality_score,engagement_score,monetization_fit_score,
                        policy_risk_score,feasibility_score,total_score,score_evidence,
                        generation_evidence,review_rationale,reviewed_by,reviewed_at,
                        accepted_plan_id,accepted_content_id)
                       VALUES (%s,%s,'accepted',%s,%s,%s,'vertical_short','education',%s,
                               'low','low',0,'local',%s,%s,ARRAY['controlled','original'],
                               95,90,85,5,95,92,'{"reviewed":true}'::jsonb,
                               '{"adapter":"deterministic"}'::jsonb,%s,'reviewer.one',now(),%s,%s)""",
                    (
                        batch["id"],
                        ordinal,
                        f"{name} accepted concept {ordinal}",
                        f"A factual hook for {name} item {ordinal}",
                        f"An original controlled concept explaining a mechanism for {name} item {ordinal}.",
                        "The concept is original, factual, bounded, and feasible for the acceptance pilot.",
                        (marker + str(ordinal)) * 32,
                        f"p100-bootstrap-{slug}-{ordinal}",
                        "Reviewed for originality, feasibility, and factual scope.",
                        plan["id"],
                        content["id"],
                    ),
                )
                brand_contents.append(dict(content))
            result["brands"][slug] = brand["id"]
            result["contents"][slug] = brand_contents

    scripts = ScriptReviewService(database)
    seed_value = 700
    for slug in ("animal-x", "rawr-nation"):
        for ordinal, content in enumerate(result["contents"][slug], start=1):
            seed_value += 1
            initialized = scripts.initialize(
                content_id=content["id"],
                request=script_request(seed_value),
                actor="producer.one",
            )
            document_id = initialized["document"]["id"]
            supported = scripts.update_source_support(
                document_id=document_id,
                request=source_request(
                    expected_lock=1,
                    suffix=f"{slug}-{ordinal}",
                ),
                actor="producer.one",
            )
            submitted = scripts.submit(
                document_id=document_id,
                expected_lock_version=supported["document"]["lock_version"],
                actor="producer.one",
            )
            scripts.decide(
                document_id=document_id,
                expected_lock_version=submitted["document"]["lock_version"],
                decision=ScriptDecision.APPROVED,
                rationale="Concept, claims, sources, scenes, and duration are acceptable.",
                reviewer="reviewer.one",
            )
    return result


def payload_for(ready, *, pilot_key: str = "p100-controlled-bootstrap") -> dict:
    animal = ready["contents"]["animal-x"]
    rawr = ready["contents"]["rawr-nation"]
    return {
        "pilot_key": pilot_key,
        "acceptance_policy": {
            "critical_defects_allowed": 0,
            "major_defects_allowed": 0,
        },
        "items": [
            {
                "portfolio_content_id": str(animal[0]["id"]),
                "content_version": int(animal[0]["version"]),
                "production_mode": "local_only",
                "live_delivery_evidence_required": False,
            },
            {
                "portfolio_content_id": str(animal[1]["id"]),
                "content_version": int(animal[1]["version"]),
                "production_mode": "managed_render",
                "live_delivery_evidence_required": False,
            },
            {
                "portfolio_content_id": str(rawr[0]["id"]),
                "content_version": int(rawr[0]["version"]),
                "production_mode": "local_only",
                "live_delivery_evidence_required": False,
            },
            {
                "portfolio_content_id": str(rawr[1]["id"]),
                "content_version": int(rawr[1]["version"]),
                "production_mode": "managed_render",
                "live_delivery_evidence_required": True,
            },
        ],
    }


def state_counts(database) -> dict[str, int]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT
                 (SELECT count(*) FROM football_brief.acceptance_pilots) AS pilots,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_items) AS pilot_items,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_events) AS events,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_evidence) AS evidence,
                 (SELECT count(*) FROM football_brief.generation_jobs) AS generation_jobs,
                 (SELECT count(*) FROM football_brief.production_spend_reservations) AS reservations,
                 (SELECT count(*) FROM football_brief.platform_delivery_requests) AS deliveries,
                 (SELECT count(*) FROM football_brief.final_releases) AS releases"""
        ).fetchone()
    return {key: int(row[key]) for key in row.keys()}


def test_controlled_bootstrap_is_atomic_idempotent_and_draft_only(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    client = bootstrap_client(p89_database)
    path = "/acceptance/pilots/bootstrap-draft"
    assert path in {route.path for route in client.app.routes}

    request = payload_for(ready)
    denied = client.post(path, headers={"X-Operator-Key": "producer-key"}, json=request)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "admin_required"

    before = state_counts(p89_database)
    created = client.post(path, headers={"X-Operator-Key": "admin-key"}, json=request)
    assert created.status_code == 200, created.text
    result = created.json()
    assert result["kind"] == "p100_controlled_draft_bootstrap"
    assert result["reused"] is False
    assert result["pilot"]["status"] == "draft"
    assert len(result["items"]) == 4
    assert result["readiness"]["scope"]["passed"] is True
    assert result["readiness"]["ready_for_signoff"] is False
    assert result["readiness"]["ready_for_acceptance"] is False
    assert result["runbook"]["sha256"]
    pilot_id = result["pilot"]["id"]
    item_ids = [item["id"] for item in result["items"]]

    after_create = state_counts(p89_database)
    assert after_create["pilots"] == before["pilots"] + 1
    assert after_create["pilot_items"] == before["pilot_items"] + 4
    assert after_create["events"] == before["events"] + 5
    assert after_create["evidence"] == before["evidence"]
    assert after_create["generation_jobs"] == before["generation_jobs"]
    assert after_create["reservations"] == before["reservations"]
    assert after_create["deliveries"] == before["deliveries"]
    assert after_create["releases"] == before["releases"]

    replay = client.post(path, headers={"X-Operator-Key": "admin-key"}, json=request)
    assert replay.status_code == 200, replay.text
    assert replay.json()["reused"] is True
    assert replay.json()["pilot"]["id"] == pilot_id
    assert [item["id"] for item in replay.json()["items"]] == item_ids
    assert state_counts(p89_database) == after_create

    conflict_request = payload_for(ready)
    conflict_request["items"][3]["live_delivery_evidence_required"] = False
    conflict_request["items"][0]["live_delivery_evidence_required"] = True
    conflict = client.post(
        path,
        headers={"X-Operator-Key": "admin-key"},
        json=conflict_request,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "pilot_bootstrap_key_conflict"
    assert state_counts(p89_database) == after_create

    stale_request = payload_for(ready, pilot_key="p100-bootstrap-stale")
    stale_request["items"][0]["content_version"] += 1
    stale = client.post(path, headers={"X-Operator-Key": "admin-key"}, json=stale_request)
    assert stale.status_code == 422
    assert stale.json()["detail"]["code"] == "pilot_bootstrap_stale_content_version"
    assert state_counts(p89_database) == after_create

    duplicate_request = payload_for(ready, pilot_key="p100-bootstrap-duplicate")
    duplicate_request["items"][1]["portfolio_content_id"] = duplicate_request["items"][0][
        "portfolio_content_id"
    ]
    duplicate = client.post(
        path,
        headers={"X-Operator-Key": "admin-key"},
        json=duplicate_request,
    )
    assert duplicate.status_code == 422
    assert state_counts(p89_database) == after_create

    scope_request = payload_for(ready, pilot_key="p100-bootstrap-scope")
    scope_request["items"][1]["production_mode"] = "local_only"
    scope = client.post(path, headers={"X-Operator-Key": "admin-key"}, json=scope_request)
    assert scope.status_code == 422
    assert scope.json()["detail"]["code"] == "pilot_bootstrap_scope_mismatch"
    assert state_counts(p89_database) == after_create

    bound_request = payload_for(ready, pilot_key="p100-bootstrap-bound")
    bound = client.post(path, headers={"X-Operator-Key": "admin-key"}, json=bound_request)
    assert bound.status_code == 409
    assert bound.json()["detail"]["code"] == "pilot_bootstrap_content_already_bound"
    assert state_counts(p89_database) == after_create
