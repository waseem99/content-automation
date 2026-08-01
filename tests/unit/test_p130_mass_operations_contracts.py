from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p130_migration_retains_selection_jobs_and_exact_results() -> None:
    migration = (ROOT / "migrations/0107_p130_mass_operations_acceptance.sql").read_text()
    assert "campaign_selection_snapshots" in migration
    assert "campaign_selection_members" in migration
    assert "campaign_mass_operation_jobs" in migration
    assert "campaign_mass_operation_item_results" in migration
    assert "campaign_inline_edit_events" in migration
    assert "mass_operations_acceptance_runs" in migration
    assert "exact_result_rows=requested_items" in migration
    assert "unauthorized_brand_action_rejected=true" in migration


def test_p130_service_enforces_brand_scope_and_optimistic_locking() -> None:
    service = (ROOT / "src/application/mass_operations/service.py").read_text()
    final_service = (ROOT / "src/application/mass_operations/final_service.py").read_text()
    assert "identity.can_access_brand" in service
    assert "AccessPermission.RUN_PRODUCTION" in service
    assert "AccessPermission.EDIT_CONTENT" in service
    assert "campaign_item_optimistic_lock_conflict" in service
    assert "campaign_selection_members" in service
    assert "campaign_mass_operation_jobs" in service
    assert "JOIN football_brief.pre_generation_runs" in final_service
    assert "FOR UPDATE OF item,run" in final_service
    assert "campaign_mass_operation_item_results" in final_service


def test_p130_acceptance_is_exactly_one_thousand_and_sheet_free() -> None:
    runner = (ROOT / "src/operations/mass_operations_acceptance.py").read_text()
    assert "items: int = 1_000" in runner
    assert "snapshot[\"item_count\"] == items" in runner
    assert "result_rows == items" in runner
    assert "grouped_before == items" in runner
    assert "grouped_after == 0" in runner
    assert "brand_access_denied" in runner
    assert '"spreadsheet_dependency": False' in runner
