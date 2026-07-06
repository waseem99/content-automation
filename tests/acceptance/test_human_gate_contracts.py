from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0014_human_review_service.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_human_gate_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_review_requests_capture_target_and_assignment() -> None:
    sql = _sql()
    for fragment in (
        "create table football_brief.human_review_requests",
        "target_type text not null",
        "assigned_to text",
        "requested_by text not null",
        "prevent_self_approval boolean not null default true",
        "required_checklist jsonb not null default '{}'::jsonb",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_decision_contract_requires_identity_rationale_and_checklist() -> None:
    sql = _sql()
    for fragment in (
        "reviewer identity is required",
        "review rationale is required",
        "review checklist is required",
        "disclosure decision requires disclosure text",
        "self approval is not allowed",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_decisions_are_append_only() -> None:
    sql = _sql()
    assert "human_reviews_append_only" in sql
    assert "human review decisions are append-only" in sql
