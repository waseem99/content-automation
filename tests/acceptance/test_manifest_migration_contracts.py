from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = tuple(
    ROOT / "migrations" / name
    for name in (
        "0006_immutable_render_manifests.sql",
        "0007_manifest_deferred_validation_fix.sql",
        "0008_publish_manifest_validation.sql",
        "0009_publication_reference_validation_fix.sql",
    )
)
SCHEMA = ROOT / "schemas" / "render-manifest-v1.schema.json"


def _sql(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_manifest_migrations_are_forward_only_and_transactional() -> None:
    for path in MIGRATIONS:
        sql = _sql(path)
        assert sql.startswith("-- football brief")
        assert " begin;" in f" {sql}"
        assert sql.endswith("commit;")
        assert "drop table" not in sql
        assert "drop schema" not in sql


@pytest.mark.acceptance
def test_manifest_schema_enforces_modes_and_material_hashes() -> None:
    sql = _sql(MIGRATIONS[0])
    required = (
        "status in ('draft', 'sealed', 'approved')",
        "material_input_hash char(64)",
        "script_hash char(64)",
        "storyboard_hash char(64)",
        "brand_hash char(64)",
        "policy_hash char(64)",
        "rights_gate_evaluation_id uuid",
        "approval_review_id uuid",
        "preview_manifest_is_non_publishable",
        "render_manifests_immutable",
        "render_manifest_assets_immutable",
        "publication_packages_publish_only",
    )
    for fragment in required:
        assert fragment in sql


@pytest.mark.acceptance
def test_publish_validation_requires_review_gate_rights_and_hashes() -> None:
    sql = _sql(MIGRATIONS[2])
    for fragment in (
        "approval_review_id is null",
        "rights_gate_evaluation_id is null",
        "review_decision is distinct from 'approved'",
        "gate_outcome is distinct from 'pass'",
        "asset_rights_id is null",
        "asset_sha256 <> asset.sha256",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_render_manifest_json_schema_is_valid_json() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["properties"]["mode"]["enum"] == ["preview", "publish"]
    preset = schema["$defs"]["preset"]["properties"]
    assert preset["pre_hook_intro_duration_sec"]["const"] == 0
    assert preset["logo_sting_duration_sec"]["minimum"] == 0.3
    assert preset["logo_sting_duration_sec"]["maximum"] == 0.7
