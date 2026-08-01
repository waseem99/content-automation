from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p129_migration_retains_recovery_and_scale_evidence() -> None:
    migration = (ROOT / "migrations/0106_p129_storage_scale_recovery.sql").read_text()
    assert "asset_storage_recovery_events" in migration
    assert "storage_scale_acceptance_runs" in migration
    assert "requested_locations" in migration
    assert "recovered_local_copies" in migration
    assert "canonical_identity_changes=0" in migration
    assert "drive_outage_local_failures=0" in migration
    assert "Storage recovery evidence is immutable" in migration


def test_p129_recovery_is_atomic_and_hash_verified() -> None:
    recovery = (ROOT / "src/application/campaign_storage/recovery.py").read_text()
    patch = (ROOT / "src/application/campaign_storage/download_patch.py").read_text()
    assert "drive_recovery_full_sha256" in recovery
    assert "inspection.sha256 != expected_sha" in recovery
    assert "os.replace(downloaded, destination)" in recovery
    assert "source_drive_location_id" in recovery
    assert "temporary.unlink(missing_ok=True)" in patch
    assert "os.fsync" in patch
    assert "Bearer" in patch


def test_p129_acceptance_is_exactly_100k_and_network_free() -> None:
    runner = (ROOT / "src/operations/storage_scale_acceptance.py").read_text()
    assert "assets: int = 50_000" in runner
    assert "locations: int = 100_000" in runner
    assert "locations != assets * 2" in runner
    assert "FakeDrive" in runner
    assert '"external_drive_network": False' in runner
    assert "duplicate_delta == 0" in runner
    assert "drive_outage_local_failures == 0" in runner
    assert "canonical_identity_changes == 0" in runner
