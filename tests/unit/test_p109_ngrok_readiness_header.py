from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1"
READINESS = ROOT / "scripts" / "windows" / "check_production_readiness.ps1"
WORKER_LAUNCHER = ROOT / "src" / "operations" / "local_worker_aligned.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_remote_readiness_checks_skip_ngrok_browser_warning() -> None:
    required_header = '"ngrok-skip-browser-warning" = "true"'

    assert required_header in _read(DEPLOY)
    assert required_header in _read(READINESS)


def test_local_worker_does_not_use_retired_public_producer_identity() -> None:
    source = _read(WORKER_LAUNCHER)

    assert 'LOCAL_PRODUCER_OPERATOR_ID' in source
    assert 'LOCAL_REVIEWER_OPERATOR_ID' in source
    assert '== "local-producer"' in source
    assert '"local-reviewer"' in source
