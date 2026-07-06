from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0010_voice_music_font_policy.sql"


def _sql() -> str:
    return re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8").lower()).strip()


@pytest.mark.acceptance
def test_voice_media_policy_migration_is_forward_only_and_transactional() -> None:
    sql = _sql()
    assert sql.startswith("-- football brief")
    assert " begin;" in f" {sql}"
    assert sql.endswith("commit;")
    assert "drop table" not in sql
    assert "drop schema" not in sql


@pytest.mark.acceptance
def test_approved_voice_policy_is_enforced_in_database() -> None:
    sql = _sql()
    for fragment in (
        "preview_only boolean not null default false",
        "approved_voices_policy_guard",
        "approved cloned voices require consent evidence",
        "canonical consent evidence",
        "metadata->>'evidence_type' is distinct from 'consent'",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_narration_outputs_capture_required_publish_audit_fields() -> None:
    sql = _sql()
    for fragment in (
        "create table football_brief.narration_outputs",
        "text_hash char(64) not null",
        "approved_voice_id uuid",
        "provider_request_id text not null",
        "model_id text not null",
        "output_asset_id uuid",
        "output_sha256 char(64)",
        "publish_narration_requires_approval_and_output",
        "narration_outputs_policy_guard",
    ):
        assert fragment in sql


@pytest.mark.acceptance
def test_publish_narration_fails_closed_for_preview_or_bad_voice() -> None:
    sql = _sql()
    for fragment in (
        "publish narration requires approved voice",
        "narration provider voice does not match approval",
        "publish narration voice is not currently approved",
        "voice.preview_only",
        "narration output asset hash/type mismatch",
    ):
        assert fragment in sql
