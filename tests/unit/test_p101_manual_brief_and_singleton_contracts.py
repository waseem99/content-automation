from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0091_studio_manual_brief_event.sql"
STUDIO = ROOT / "src" / "operator_api" / "studio_v2_runtime.py"
INSTALLER = ROOT / "scripts" / "windows" / "install_local_production_service.ps1"
ALWAYS_ON = ROOT / "scripts" / "windows" / "supervise_always_on_local_production.ps1"


def test_manual_brief_event_matches_the_forward_schema_contract() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    studio = STUDIO.read_text(encoding="utf-8")

    assert "DROP CONSTRAINT production_workflow_stage_history_event_check" in migration
    assert "ADD CONSTRAINT production_workflow_stage_history_event_check" in migration
    assert "'manual_brief_accepted'" in migration
    assert "'manual_brief_accepted'" in studio


def test_service_installer_replaces_an_existing_runtime_before_starting() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "Stop-ScheduledTask -TaskName $TaskName" in installer
    assert 'New-Item -ItemType File -Force -Path $StopMarker' in installer
    assert 'taskkill.exe /PID $process.ProcessId /T /F' in installer
    assert 'src\\.operator_api\\.entrypoint:app' in installer
    assert 'src\\.operations\\.local_worker_aligned' in installer
    assert 'src\\.operations\\.always_on_continuation' in installer
    assert installer.index("Stop-ExistingLocalRuntime") < installer.index("Register-ScheduledTask")
    assert "-MultipleInstances IgnoreNew" in installer


def test_always_on_wrapper_holds_a_lock_and_waits_for_core_cleanup() -> None:
    always_on = ALWAYS_ON.read_text(encoding="utf-8")

    assert 'always-on-supervisor.lock' in always_on
    assert "[System.IO.FileShare]::None" in always_on
    assert "Another always-on Content Automation supervisor already owns this runtime." in always_on
    assert "The core supervisor watches the same marker" in always_on
    assert "continue" in always_on
    assert "$lockStream.Dispose()" in always_on
