"""Static acceptance contracts for the Phase 0 and Phase 1 SQL migrations.

These tests run without a database and protect the initial migration files from
accidental removal of required audit, rights, idempotency, and render controls.
A PostgreSQL integration suite must be added when the database runtime is wired.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PHASE_0 = ROOT / "migrations" / "0001_phase0_asset_rights.sql"
PHASE_1 = ROOT / "migrations" / "0002_phase1_workflow_foundation.sql"


def _sql(path: Path) -> str:
    assert path.exists(), f"Missing migration: {path}"
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_migrations_are_transactional_and_forward_only() -> None:
    for path in (PHASE_0, PHASE_1):
        sql = _sql(path)
        assert sql.startswith("-- football brief")
        assert " begin;" in f" {sql}"
        assert sql.endswith("commit;")
        assert "drop table" not in sql
        assert "drop schema" not in sql


@pytest.mark.acceptance
def test_phase_0_creates_required_rights_tables() -> None:
    sql = _sql(PHASE_0)
    required_tables = (
        "football_brief.assets",
        "football_brief.rights_evidence",
        "football_brief.asset_rights",
        "football_brief.approved_voices",
    )
    for table in required_tables:
        assert f"create table {table}" in sql


@pytest.mark.acceptance
def test_phase_0_contains_fail_closed_rights_fields() -> None:
    sql = _sql(PHASE_0)
    required_fragments = (
        "commercial_use_allowed boolean not null default false",
        "editorial_use_allowed boolean not null default false",
        "modification_allowed boolean not null default false",
        "synthetic_edit_allowed boolean not null default false",
        "attribution_required boolean not null default false",
        "approval_status text not null default 'pending'",
        "approved_rights_have_approver",
        "rights_attribution_present",
        "cloned_voice_requires_consent",
        "parent_asset_id uuid references football_brief.assets",
        "sha256 char(64) not null unique",
    )
    for fragment in required_fragments:
        assert fragment in sql


@pytest.mark.acceptance
def test_phase_0_does_not_default_assets_or_rights_to_approved() -> None:
    sql = _sql(PHASE_0)
    assert "lifecycle_status text not null default 'candidate'" in sql
    assert "approval_status text not null default 'pending'" in sql
    assert "commercial_use_allowed boolean not null default false" in sql


@pytest.mark.acceptance
def test_phase_1_creates_workflow_and_audit_tables() -> None:
    sql = _sql(PHASE_1)
    required_tables = (
        "football_brief.content_items",
        "football_brief.workflow_runs",
        "football_brief.stage_executions",
        "football_brief.workflow_events",
        "football_brief.human_reviews",
        "football_brief.provider_calls",
        "football_brief.cost_entries",
        "football_brief.prompt_versions",
        "football_brief.policy_versions",
        "football_brief.brand_versions",
        "football_brief.render_manifests",
        "football_brief.render_manifest_assets",
        "football_brief.render_jobs",
        "football_brief.quality_reports",
        "football_brief.operator_actions",
    )
    for table in required_tables:
        assert f"create table {table}" in sql


@pytest.mark.acceptance
def test_phase_1_enforces_idempotency_and_attempt_history() -> None:
    sql = _sql(PHASE_1)
    assert "unique (idempotency_key)" in sql
    assert "unique (provider, idempotency_key)" in sql
    assert "unique (workflow_run_id, stage_name, attempt)" in sql
    assert "attempt integer not null default 1 check (attempt >= 1)" in sql
    assert "retry_count integer not null default 0 check (retry_count >= 0)" in sql


@pytest.mark.acceptance
def test_publish_manifest_requires_human_approval_and_asset_evidence_links() -> None:
    sql = _sql(PHASE_1)
    assert "mode text not null check (mode in ('preview', 'publish'))" in sql
    assert "publish_manifest_requires_approval" in sql
    assert "asset_rights_id uuid not null references football_brief.asset_rights" in sql
    assert "asset_sha256 char(64) not null" in sql
    assert "manifest_hash char(64) not null unique" in sql


@pytest.mark.acceptance
def test_quality_outcomes_include_human_escalation_and_block() -> None:
    sql = _sql(PHASE_1)
    expected = (
        "'pass'",
        "'pass_with_disclosure'",
        "'human_review_required'",
        "'block'",
    )
    for value in expected:
        assert value in sql


@pytest.mark.acceptance
def test_cost_fields_never_allow_negative_values() -> None:
    sql = _sql(PHASE_1)
    assert "actual_cost_usd numeric(12, 4) not null default 0 check (actual_cost_usd >= 0)" in sql
    assert "cost_usd numeric(12, 4) not null default 0 check (cost_usd >= 0)" in sql
    assert "amount_usd numeric(12, 4) not null check (amount_usd >= 0)" in sql
