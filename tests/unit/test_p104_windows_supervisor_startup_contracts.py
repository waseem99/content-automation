from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ROOT / "scripts" / "windows"


def read(name: str) -> str:
    return (WINDOWS / name).read_text(encoding="utf-8")


def test_api_watchdog_allows_real_windows_startup_time() -> None:
    script = read("supervise_local_production.ps1")
    assert "$apiStartupGraceSeconds = 300" in script
    assert "$apiUnreadyCheckLimit = 60" in script
    assert ".AddSeconds($apiStartupGraceSeconds)" in script
    assert ".started_at.AddMinutes(1)" not in script


def test_all_scheduled_child_processes_are_hidden() -> None:
    core = read("supervise_local_production.ps1")
    outer = read("supervise_always_on_local_production.ps1")
    installer = read("install_local_production_service.ps1")

    assert "-WindowStyle Hidden -RedirectStandardOutput" in core
    assert "Start-Process powershell" in outer
    assert "-WindowStyle Hidden -PassThru" in outer
    assert "-WindowStyle Hidden `" in outer
    assert "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass" in installer


def test_supervisor_logs_child_exit_codes_before_restart() -> None:
    script = read("supervise_local_production.ps1")
    assert "exited with code $($State.process.ExitCode); restarting" in script
