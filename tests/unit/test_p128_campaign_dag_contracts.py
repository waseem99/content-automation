from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p128_migration_has_valid_capability_and_lease_contracts() -> None:
    migration = (ROOT / "migrations/0105_p128_campaign_dag_workers.sql").read_text()
    assert "campaign_task_graphs" in migration
    assert "campaign_task_workers" in migration
    assert "campaign_task_attempts" in migration
    assert "dag_acceptance_runs" in migration
    assert "SKIP LOCKED" not in migration
    assert "ARRAY(SELECT DISTINCT" not in migration
    assert "required_capabilities" in migration
    assert "current_lease_token" in migration
    assert "Terminal campaign tasks are immutable" in migration


def test_p128_service_uses_fair_capability_claims_and_recovery() -> None:
    service = (ROOT / "src/application/campaign_dag/service.py").read_text()
    assert "required_capabilities <@ %s::text[]" in service
    assert "CROSS JOIN LATERAL" in service
    assert "FOR UPDATE OF task SKIP LOCKED" in service
    assert "recover_stale_leases" in service
    assert "task_lease_lost" in service
    assert "terminal_output_conflict" in service
    assert "sorted({" in service


def test_p128_acceptance_is_full_target_and_non_media() -> None:
    runner = (ROOT / "src/operations/dag_acceptance.py").read_text()
    entry = (ROOT / "src/operations/dag_acceptance_entry.py").read_text()
    assert "tasks: int = 1_000_000" in runner
    assert "workers: int = 100" in runner
    assert "campaigns: int = 10" in runner
    assert "recovered_leases" in runner
    assert "fairness_spread" in runner
    assert "paid_execution\": False" in runner
    assert "publishing\": False" in runner
    assert "RETURNING *" in entry
    assert "cursor.rowcount" in entry
    assert "priority=1000" in entry
