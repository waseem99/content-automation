from __future__ import annotations

import pytest

from src.application.acceptance.controlled_snapshot_models import (
    PilotEvidenceSnapshotRequest,
)
from src.application.acceptance.controlled_snapshot_service import (
    ControlledEvidenceSnapshotService,
)
from src.application.acceptance.service import CONTENT_CATEGORIES
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.test_p100_controlled_draft_bootstrap import (
    seed_selectable_contents,
    state_counts,
)
from tests.integration.test_p100_controlled_pilot_start import (
    bootstrap_pilot,
    controlled_start_client,
    start_payload,
)


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def snapshot_payload(preview: dict) -> dict:
    return {
        "bootstrap_request_sha256": preview["bootstrap_request_sha256"],
        "controlled_start_event_sha256": preview[
            "controlled_start_event_sha256"
        ],
        "runbook_sha256": preview["runbook"]["sha256"],
        "snapshot_sha256": preview["snapshot_sha256"],
        "started_at": preview["started_at"],
    }


def evidence_side_effect_counts(database, pilot_id) -> dict[str, int]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT
                 (SELECT count(*) FROM football_brief.acceptance_pilot_signoffs
                   WHERE pilot_id=%s) AS signoffs,
                 (SELECT count(*) FROM football_brief.acceptance_live_delivery_evidence
                   WHERE pilot_id=%s) AS live_results,
                 (SELECT count(*) FROM football_brief.operations_restore_events) AS restores,
                 (SELECT count(*) FROM football_brief.operations_drill_runs) AS drills""",
            (pilot_id, pilot_id),
        ).fetchone()
    return {key: int(row[key]) for key in row.keys()}


def start_controlled_pilot(database, ready) -> tuple[dict, object]:
    bootstrap = bootstrap_pilot(database, ready)
    client = controlled_start_client(database)
    pilot_id = bootstrap["pilot"]["id"]
    started = client.post(
        f"/acceptance/pilots/{pilot_id}/start-controlled",
        headers={"X-Operator-Key": "admin-key"},
        json=start_payload(bootstrap),
    )
    assert started.status_code == 200, started.text
    return bootstrap, client


def test_controlled_snapshot_is_scoped_atomic_versioned_and_idempotent(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    bootstrap, client = start_controlled_pilot(p89_database, ready)
    pilot_id = bootstrap["pilot"]["id"]
    preview_path = f"/acceptance/pilots/{pilot_id}/evidence-preview"
    snapshot_path = f"/acceptance/pilots/{pilot_id}/snapshot-evidence"
    routes = {route.path for route in client.app.routes}
    assert "/acceptance/pilots/{pilot_id}/evidence-preview" in routes
    assert "/acceptance/pilots/{pilot_id}/snapshot-evidence" in routes

    for key in ("producer-key", "publisher-key"):
        denied = client.get(preview_path, headers={"X-Operator-Key": key})
        assert denied.status_code == 403
        assert denied.json()["detail"] == "acceptance_snapshot_role_required"

    before_preview = state_counts(p89_database)
    reviewer_preview = client.get(
        preview_path,
        headers={"X-Operator-Key": "reviewer-key"},
    )
    assert reviewer_preview.status_code == 200, reviewer_preview.text
    preview = reviewer_preview.json()
    assert preview["kind"] == "p100_controlled_evidence_preview"
    assert preview["pilot_status"] == "running"
    assert preview["snapshot_ready"] is True
    assert preview["all_content_passed"] is False
    assert preview["scope"]["passed"] is True
    assert len(preview["items"]) == 4
    assert all(
        item["required_categories"] == len(CONTENT_CATEGORIES)
        for item in preview["items"]
    )
    assert state_counts(p89_database) == before_preview

    wrong_identity = snapshot_payload(preview)
    wrong_identity["snapshot_sha256"] = "0" * 64
    rejected = client.post(
        snapshot_path,
        headers={"X-Operator-Key": "reviewer-key"},
        json=wrong_identity,
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "pilot_snapshot_identity_mismatch"
    assert state_counts(p89_database) == before_preview

    before_side_effects = evidence_side_effect_counts(p89_database, pilot_id)
    recorded = client.post(
        snapshot_path,
        headers={"X-Operator-Key": "reviewer-key"},
        json=snapshot_payload(preview),
    )
    assert recorded.status_code == 200, recorded.text
    result = recorded.json()
    assert result["kind"] == "p100_controlled_evidence_snapshot"
    assert result["reused"] is False
    assert result["ok"] is False
    assert result["pilot"]["status"] == "blocked"
    assert len(result["items"]) == 4
    assert all(item["status"] == "blocked" for item in result["items"])
    assert result["evidence_inserted"] == len(CONTENT_CATEGORIES) * 4
    assert result["evidence_reused"] == 0

    after_first = state_counts(p89_database)
    assert after_first["evidence"] == before_preview["evidence"] + len(CONTENT_CATEGORIES) * 4
    assert after_first["events"] == before_preview["events"] + 5
    for key in (
        "pilots",
        "pilot_items",
        "generation_jobs",
        "reservations",
        "deliveries",
        "releases",
    ):
        assert after_first[key] == before_preview[key]
    assert evidence_side_effect_counts(p89_database, pilot_id) == before_side_effects

    blocked_preview = client.get(
        preview_path,
        headers={"X-Operator-Key": "admin-key"},
    )
    assert blocked_preview.status_code == 200
    blocked_report = blocked_preview.json()
    assert blocked_report["pilot_status"] == "blocked"
    assert blocked_report["snapshot_sha256"] == preview["snapshot_sha256"]
    replay = client.post(
        snapshot_path,
        headers={"X-Operator-Key": "admin-key"},
        json=snapshot_payload(blocked_report),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["reused"] is True
    assert replay.json()["evidence_inserted"] == 0
    assert state_counts(p89_database) == after_first

    with p89_database.transaction() as conn:
        extra_reviewer = conn.execute(
            """INSERT INTO football_brief.operator_users
               (operator_id,display_name,created_by)
               VALUES ('reviewer.snapshot.extra','Snapshot Extra Reviewer','admin.one')
               RETURNING id"""
        ).fetchone()
        conn.execute(
            """INSERT INTO football_brief.operator_user_roles
               (operator_user_id,role,assigned_by)
               VALUES (%s,'reviewer','admin.one')""",
            (extra_reviewer["id"],),
        )
        for brand_id in ready["brands"].values():
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,'admin.one')""",
                (extra_reviewer["id"], brand_id),
            )

    changed_preview = client.get(
        preview_path,
        headers={"X-Operator-Key": "reviewer-key"},
    )
    assert changed_preview.status_code == 200
    changed_report = changed_preview.json()
    assert changed_report["snapshot_sha256"] != preview["snapshot_sha256"]
    changed = client.post(
        snapshot_path,
        headers={"X-Operator-Key": "reviewer-key"},
        json=snapshot_payload(changed_report),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["reused"] is False
    assert changed.json()["evidence_inserted"] == 4
    after_changed = state_counts(p89_database)
    assert after_changed["evidence"] == after_first["evidence"] + 4
    assert after_changed["events"] == after_first["events"] + 4
    assert evidence_side_effect_counts(p89_database, pilot_id) == before_side_effects


def test_controlled_snapshot_rolls_back_every_write_on_mid_batch_failure(
    p89_database,
    p89_seeded,
    monkeypatch,
) -> None:
    ready = seed_selectable_contents(p89_database, p89_seeded)
    bootstrap, _client = start_controlled_pilot(p89_database, ready)
    pilot_id = bootstrap["pilot"]["id"]
    service = ControlledEvidenceSnapshotService(p89_database)
    preview = service.preview(pilot_id=pilot_id)
    request = PilotEvidenceSnapshotRequest(**snapshot_payload(preview))
    before = state_counts(p89_database)
    before_side_effects = evidence_side_effect_counts(p89_database, pilot_id)
    original = service._record_evidence
    calls = {"count": 0}

    def fail_after_first(conn, *, item_id, category, result, actor):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("forced controlled snapshot rollback")
        return original(
            conn,
            item_id=item_id,
            category=category,
            result=result,
            actor=actor,
        )

    monkeypatch.setattr(service, "_record_evidence", fail_after_first)
    with pytest.raises(RuntimeError, match="forced controlled snapshot rollback"):
        service.snapshot(
            pilot_id=pilot_id,
            request=request,
            actor="admin.one",
        )

    assert state_counts(p89_database) == before
    assert evidence_side_effect_counts(p89_database, pilot_id) == before_side_effects
    with p89_database.connection() as conn:
        pilot = conn.execute(
            "SELECT status FROM football_brief.acceptance_pilots WHERE id=%s",
            (pilot_id,),
        ).fetchone()
        items = conn.execute(
            "SELECT status FROM football_brief.acceptance_pilot_items WHERE pilot_id=%s",
            (pilot_id,),
        ).fetchall()
    assert pilot["status"] == "running"
    assert {row["status"] for row in items} == {"pending"}
