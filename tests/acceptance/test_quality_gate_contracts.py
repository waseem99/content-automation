from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0012_publish_quality_gate.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_quality_gate_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_quality_reports_capture_structured_evidence() -> None:
    sql = _sql()
    for fragment in (
        "alter table football_brief.quality_reports",
        "check_registry_version text not null default 'quality-gate-v1'",
        "input_hash char(64)",
        "output_hash char(64)",
        "report_hash char(64)",
        "disclosure_texts jsonb not null default '[]'::jsonb",
        "human_review_reasons jsonb not null default '[]'::jsonb",
        "quality_reports_contract_guard",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_report_contract_requires_reasons_for_non_plain_passes() -> None:
    sql = _sql()
    for fragment in (
        "pass_with_disclosure requires disclosure text",
        "human_review_required requires human review reasons",
        "block quality reports require blocking failures",
        "quality report output hash does not match asset",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_publication_package_is_guarded_by_latest_quality_report() -> None:
    sql = _sql()
    for fragment in (
        "alter table football_brief.publication_packages",
        "quality_report_id uuid references football_brief.quality_reports",
        "publication_package_quality_gate",
        "publication packages require a quality report",
        "publication packages require a passing quality report",
        "publication package quality report does not match render output",
        "quality_status",
        "disclosure_texts",
    ):
        assert fragment in sql
