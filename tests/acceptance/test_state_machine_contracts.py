from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0013_workflow_state_machine.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_state_machine_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_stage_dependencies_are_recorded_for_invalidation() -> None:
    sql = _sql()
    for fragment in (
        "create table football_brief.stage_dependencies",
        "upstream_stage_execution_id uuid not null",
        "downstream_stage_execution_id uuid not null",
        "expected_upstream_output_hash char(64)",
        "stage_dependencies_workflow_idx",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_status_changes_are_guarded_by_state_machine_setting() -> None:
    sql = _sql()
    for fragment in (
        "workflow_runs_state_machine_guard",
        "stage_executions_state_machine_guard",
        "current_setting('football_brief.state_machine', true)",
        "workflow status changes must use state machine service",
        "stage status changes must use state machine service",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_workflow_events_are_append_only() -> None:
    sql = _sql()
    assert "workflow_events_append_only" in sql
    assert "workflow events are append-only" in sql
