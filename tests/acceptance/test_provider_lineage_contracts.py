from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0011_provider_generation_lineage.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_provider_lineage_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_provider_generation_evidence_is_immutable_and_specific() -> None:
    sql = _sql()
    for fragment in (
        "create table football_brief.provider_generation_evidence",
        "provider_call_id uuid not null unique",
        "output_asset_id uuid not null unique",
        "parent_asset_id uuid",
        "request_fingerprint char(64) not null",
        "response_fingerprint char(64) not null",
        "provider_request_id text not null",
        "input_asset_sha256 char(64)",
        "output_asset_sha256 char(64) not null",
        "provider_generation_evidence_immutable",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_provider_generation_validation_links_parent_call_stage_and_hashes() -> None:
    sql = _sql()
    for fragment in (
        "output_asset.sha256 is distinct from new.output_asset_sha256",
        "output_asset.parent_asset_id is distinct from new.parent_asset_id",
        "parent_asset.sha256 is distinct from new.input_asset_sha256",
        "call_row.status <> 'succeeded'",
        "call_row.request_fingerprint is distinct from new.request_fingerprint",
        "call_row.response_fingerprint is distinct from new.response_fingerprint",
        "stage_row.workflow_run_id is distinct from new.workflow_run_id",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_publish_manifest_generated_assets_require_evidence() -> None:
    sql = _sql()
    assert "publish_manifest_generated_asset_evidence" in sql
    assert "manifest_mode <> 'publish'" in sql
    assert "asset_row.source_type = 'ai_generated'" in sql
    assert "generated assets require provider generation evidence" in sql
