from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RIGHTS_GATE = ROOT / "migrations" / "0004_rights_gate_audit.sql"
TRIGGER_FIX = ROOT / "migrations" / "0005_rights_gate_trigger_fix.sql"


def _sql(path: Path) -> str:
    assert path.exists(), f"Missing migration: {path}"
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_rights_gate_migrations_are_transactional() -> None:
    for path in (RIGHTS_GATE, TRIGGER_FIX):
        sql = _sql(path)
        assert " begin;" in f" {sql}"
        assert sql.endswith("commit;")
        assert "drop table" not in sql
        assert "drop schema" not in sql


@pytest.mark.acceptance
def test_rights_versions_link_to_specific_evidence() -> None:
    sql = _sql(RIGHTS_GATE)
    assert "create table football_brief.asset_rights_evidence_links" in sql
    assert "primary key (asset_rights_id, rights_evidence_id)" in sql
    assert "validate_rights_evidence_asset_match" in sql
    assert "approved_rights_require_evidence" in sql
    assert "deferrable initially deferred" in sql


@pytest.mark.acceptance
def test_rights_decisions_are_append_only_and_versioned() -> None:
    sql = _sql(RIGHTS_GATE)
    required = (
        "create table football_brief.rights_gate_evaluations",
        "create table football_brief.rights_gate_asset_decisions",
        "policy_version text not null",
        "policy_hash char(64) not null",
        "evaluation_fingerprint char(64) not null",
        "reject_rights_audit_mutation",
        "before update or delete",
    )
    for fragment in required:
        assert fragment in sql


@pytest.mark.acceptance
def test_trigger_fix_handles_both_trigger_row_types() -> None:
    sql = _sql(TRIGGER_FIX)
    assert "if tg_table_name = 'asset_rights'" in sql
    assert "target_rights_id := new.id" in sql
    assert "target_rights_id := old.asset_rights_id" in sql
    assert "if tg_op = 'delete'" in sql
