from __future__ import annotations

from pathlib import Path

from src.operations.scale_benchmark import (
    CHECK_INSERT_RUN_BATCH,
    MAX_ITEMS_PER_REQUEST,
    run_benchmark,
)


ROOT = Path(__file__).resolve().parents[2]


def test_scale_benchmark_is_callable() -> None:
    assert callable(run_benchmark)
    assert MAX_ITEMS_PER_REQUEST == 10_000
    assert CHECK_INSERT_RUN_BATCH == 250


def test_scale_migration_records_control_plane_evidence() -> None:
    migration = (ROOT / "migrations" / "0102_p125_scale_benchmarks.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE football_brief.scale_benchmark_runs" in migration
    assert "requested_items integer" in migration
    assert "requested_checks bigint" in migration
    assert "final-video rendering capacity" in migration


def test_benchmark_supports_target_scale_and_idempotent_replay() -> None:
    source = (ROOT / "src" / "operations" / "scale_benchmark.py").read_text(encoding="utf-8")
    assert "items <= 20000" in source
    assert "5_000_000" in source
    assert "MAX_ITEMS_PER_REQUEST = 10_000" in source
    assert "CHECK_INSERT_RUN_BATCH = 250" in source
    assert "def _add_item_chunks" in source
    assert "for chunk in _chunks(items)" in source
    assert "def _insert_retained_checks_in_batches" in source
    assert "for run_batch in _chunks(run_ids, run_batch_size)" in source
    assert "SELECT unnest(%s::uuid[]) AS id" in source
    assert "duplicate_item_rows = max(0" in source
    assert "ON CONFLICT (run_id,stage,check_key,rule_version) DO NOTHING" in source
    assert "idempotent_item_replay" in source
    assert "idempotent_check_replay" in source
    assert '"check_batches": check_insert_batches' in source
    assert '"final_video_generation_measured": False' in source


def test_manual_workflow_defaults_to_10000_items_and_one_million_checks() -> None:
    workflow = (ROOT / ".github" / "workflows" / "p125-scale-benchmarks.yml").read_text(encoding="utf-8")
    assert 'default: "10000"' in workflow
    assert 'default: "100"' in workflow
    assert "expected_checks = expected_items" in workflow
    assert "BENCHMARK_ITEMS: ${{ github.event_name == 'workflow_dispatch' && inputs.items || '10000' }}" in workflow
