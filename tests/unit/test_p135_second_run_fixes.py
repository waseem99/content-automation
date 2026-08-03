from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from src.operations.settings import OperationsSettings
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.operations_monitoring_patch import install_operations_monitoring_route
from src.operator_api.studio_v2_security_patch import safe_team_keys_payload


ROOT = Path(__file__).resolve().parents[2]


def test_windows_bom_team_key_file_is_read_without_exposing_admin_keys(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "operator-keys.json"
    path.write_text(
        json.dumps(
            {
                "local-super-admin": "super-secret",
                "local-admin": "admin-secret",
                "local-reviewer": "reviewer-secret",
                "local-producer": "producer-secret",
                "local-publisher": "publisher-secret",
                "custom-admin": "must-not-leak",
            }
        ),
        encoding="utf-8-sig",
    )
    monkeypatch.setenv("OPS_ENVIRONMENT", "staging")
    monkeypatch.setenv("STUDIO_OPERATOR_KEYS_FILE", str(path))

    payload = safe_team_keys_payload()

    assert payload["admin_keys_exposed"] is False
    assert payload["items"] == [
        {"operator_id": "local-producer", "key": "producer-secret"},
        {"operator_id": "local-publisher", "key": "publisher-secret"},
        {"operator_id": "local-reviewer", "key": "reviewer-secret"},
    ]
    assert "super-secret" not in json.dumps(payload)
    assert "admin-secret" not in json.dumps(payload)
    assert "must-not-leak" not in json.dumps(payload)


def test_operations_monitoring_get_route_is_registered_without_mutation() -> None:
    app = FastAPI()
    install_operations_monitoring_route(
        app,
        database=None,
        auth_settings=OperatorAuthSettings(),
        operations_settings=OperationsSettings(),
    )

    route = next(route for route in app.routes if route.path == "/operations/monitoring")
    assert route.methods == {"GET"}


def test_runtime_installs_security_and_monitoring_patches() -> None:
    entrypoint = (ROOT / "src/operator_api/entrypoint.py").read_text(encoding="utf-8")
    factory = (ROOT / "src/operator_api/runtime_factory.py").read_text(encoding="utf-8")

    assert "apply_studio_v2_security_patch()" in entrypoint
    assert "install_operations_monitoring_route(" in factory


def test_scheduled_runtime_refreshes_release_identity_before_start() -> None:
    supervisor = (
        ROOT / "scripts/windows/supervise_always_on_local_production.ps1"
    ).read_text(encoding="utf-8")

    sync_call = '& $SyncP131 -Path $EnvPath'
    assert sync_call in supervisor
    assert supervisor.index(sync_call) < supervisor.index("$core = Start-CoreSupervisor")


def test_acceptance_runner_rejects_a_stale_runtime() -> None:
    runner = (
        ROOT / "scripts/windows/run_platform_acceptance.ps1"
    ).read_text(encoding="utf-8")
    readiness = (ROOT / "tests/e2e/00-readiness.spec.js").read_text(encoding="utf-8")

    assert "PLATFORM_EXPECTED_GIT_SHA" in runner
    assert "The runtime is stale" in runner
    assert "payload.release?.git_sha).toBe(expectedGitSha)" in readiness


def test_playwright_uses_document_title_assertion() -> None:
    readiness = (ROOT / "tests/e2e/00-readiness.spec.js").read_text(encoding="utf-8")

    assert "expect(page).toHaveTitle(/Content Engine Studio/)" in readiness
    assert "locator('title')" not in readiness
