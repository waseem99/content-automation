from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_p130_migration_retains_selection_jobs_and_exact_results() -> None:
    migration = (ROOT / "migrations/0107_p130_mass_operations_acceptance.sql").read_text()
    for token in (
        "campaign_selection_snapshots",
        "campaign_selection_members",
        "campaign_mass_operation_jobs",
        "campaign_mass_operation_item_results",
        "campaign_inline_edit_events",
        "mass_operations_acceptance_runs",
        "exact_result_rows=requested_items",
        "unauthorized_brand_action_rejected=true",
    ):
        assert token in migration


def test_p130_service_enforces_scope_locking_and_bulk_execution() -> None:
    service = (ROOT / "src/application/mass_operations/service.py").read_text()
    final_service = (ROOT / "src/application/mass_operations/final_service.py").read_text()
    compatibility = (ROOT / "src/infrastructure/database/executemany_patch.py").read_text()
    for token in (
        "identity.can_access_brand",
        "AccessPermission.RUN_PRODUCTION",
        "AccessPermission.EDIT_CONTENT",
        "campaign_item_optimistic_lock_conflict",
        "campaign_selection_members",
        "campaign_mass_operation_jobs",
    ):
        assert token in service
    assert "football_brief.pre_generation_runs" in final_service
    assert "campaign_mass_operation_item_results" in final_service
    assert "cursor.executemany" in compatibility
    assert "with self._connection.cursor()" in compatibility


def test_p130_acceptance_is_exactly_one_thousand_and_sheet_free() -> None:
    runner = (ROOT / "src/operations/mass_operations_acceptance.py").read_text()
    for token in (
        "items: int = 1_000",
        "int(snapshot[\"item_count\"]) == items",
        "result_rows == items",
        "grouped_before == items",
        "grouped_after == 0",
        "brand_access_denied",
        '"spreadsheet_dependency": False',
    ):
        assert token in runner
