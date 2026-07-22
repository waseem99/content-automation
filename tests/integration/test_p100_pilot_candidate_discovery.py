from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import PilotCreateRequest, PilotItemRequest, ProductionMode
from src.operations.settings import OperationsSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.test_p100_acceptance_foundation import seed_pilot_contents


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def candidate_client(database) -> TestClient:
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": "admin.one",
            "producer-key": "producer.one",
            "reviewer-key": "reviewer.one",
            "publisher-key": "publisher.p100",
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
            release_key="p100-candidate-discovery-test",
            git_sha="1" * 40,
            image_digest="sha256:" + "2" * 64,
            configuration_digest="3" * 64,
            migration_head="0089_acceptance_runbook_drill.sql",
            requests_per_minute=1000,
            storage_capacity_bytes=1024 * 1024,
        ),
    )
    return TestClient(app)


def assign_reviewer_to_required_brands(database, brand_ids) -> None:
    with database.transaction() as conn:
        reviewer = conn.execute(
            "SELECT id FROM football_brief.operator_users WHERE operator_id='reviewer.one'"
        ).fetchone()
        for brand_id in brand_ids:
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,'admin.one') ON CONFLICT DO NOTHING""",
                (reviewer["id"], brand_id),
            )


def mutation_counts(database) -> tuple[int, ...]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT
                 (SELECT count(*) FROM football_brief.acceptance_pilots) AS pilots,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_items) AS pilot_items,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_evidence) AS evidence,
                 (SELECT count(*) FROM football_brief.acceptance_pilot_events) AS events,
                 (SELECT count(*) FROM football_brief.generation_jobs) AS generation_jobs,
                 (SELECT count(*) FROM football_brief.production_spend_reservations) AS reservations"""
        ).fetchone()
    return tuple(int(row[key]) for key in row.keys())


def test_candidate_inventory_is_deterministic_mode_aware_and_read_only(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_pilot_contents(p89_database, p89_seeded)
    service = AcceptancePilotService(p89_database)
    pilot = service.create(
        PilotCreateRequest(
            pilot_key="p100-candidate-binding-test",
            acceptance_policy={"critical_defects_allowed": 0, "major_defects_allowed": 0},
        ),
        actor=str(p89_seeded["admin"]),
    )["pilot"]
    bound_content = ready["contents"]["animal-x"][0]
    service.add_item(
        pilot_id=pilot["id"],
        request=PilotItemRequest(
            portfolio_content_id=bound_content["id"],
            content_version=int(bound_content["version"]),
            production_mode=ProductionMode.LOCAL_ONLY,
        ),
        actor=str(p89_seeded["admin"]),
    )

    client = candidate_client(p89_database)
    path = "/acceptance/pilot-candidates?limit_per_brand=10"
    registered_paths = {route.path for route in client.app.routes}
    assert "/acceptance/pilot-candidates" in registered_paths

    producer = client.get(path, headers={"X-Operator-Key": "producer-key"})
    assert producer.status_code == 403
    assert producer.json()["detail"] == "acceptance_read_role_required"

    unassigned_reviewer = client.get(path, headers={"X-Operator-Key": "reviewer-key"})
    assert unassigned_reviewer.status_code == 403
    assert unassigned_reviewer.json()["detail"] == "pilot_brand_scope_required"

    before = mutation_counts(p89_database)
    first = client.get(path, headers={"X-Operator-Key": "admin-key"})
    second = client.get(path, headers={"X-Operator-Key": "admin-key"})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()

    report = first.json()
    assert report["kind"] == "p100_pilot_candidate_inventory"
    assert report["required_brand_slugs"] == ["animal-x", "rawr-nation"]
    assert len(report["candidates"]) == 4
    assert report["brands"]["animal-x"]["candidate_count"] == 2
    assert report["brands"]["rawr-nation"]["candidate_count"] == 2
    assert report["ready_to_select_four_production_complete_items"] is False

    for candidate in report["candidates"]:
        assert set(candidate["modes"]) == {"local_only", "managed_render"}
        local = candidate["modes"]["local_only"]
        managed = candidate["modes"]["managed_render"]
        assert local["canonical_required_count"] == managed["canonical_required_count"]
        assert local["rank_within_brand"] >= 1
        assert managed["rank_within_brand"] >= 1
        assert "zero_cost_local_routing_not_complete" in local["mode_blockers"]
        assert "managed_spend_reconciliation_not_complete" in managed["mode_blockers"]
        assert "managed_renderer_lineage_not_complete" in managed["mode_blockers"]

    bound = next(
        candidate
        for candidate in report["candidates"]
        if candidate["portfolio_content_id"] == str(bound_content["id"])
    )
    assert bound["already_bound_to_active_or_accepted_pilot"] is True
    assert bound["pilot_bindings"][0]["pilot_status"] == "draft"
    assert "already_bound_to_active_or_accepted_pilot" in bound["modes"]["local_only"]["selection_blockers"]

    publisher = client.get(path, headers={"X-Operator-Key": "publisher-key"})
    assert publisher.status_code == 200, publisher.text

    assign_reviewer_to_required_brands(
        p89_database,
        (ready["brands"]["animal-x"], ready["brands"]["rawr-nation"]),
    )
    reviewer = client.get(path, headers={"X-Operator-Key": "reviewer-key"})
    assert reviewer.status_code == 200, reviewer.text

    invalid_limit = client.get(
        "/acceptance/pilot-candidates?limit_per_brand=0",
        headers={"X-Operator-Key": "admin-key"},
    )
    assert invalid_limit.status_code == 422

    after = mutation_counts(p89_database)
    assert after == before
