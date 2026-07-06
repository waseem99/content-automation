from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0015_budget_controls.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_budget_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_provider_call_fields_are_extended() -> None:
    sql = _sql()
    assert "alter table football_brief.provider_calls" in sql
    assert "model_id text" in sql
    assert "latency_ms integer" in sql
    assert "pricing_profile text" in sql
    assert "budget_policy_version text" in sql


@pytest.mark.acceptance
def test_cost_rows_are_append_only_and_roll_up() -> None:
    sql = _sql()
    assert "alter table football_brief.cost_entries" in sql
    assert "reconciliation_key text" in sql
    assert "cost_entries_apply_totals" in sql
    assert "cost_entries_append_only" in sql
