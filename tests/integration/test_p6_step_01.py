from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.operator_api.entrypoint import (
    APP_IMPORT_PATH,
    FACTORY_IMPORT_PATH,
    app,
    create_runtime_app,
    runtime_metadata,
    runtime_start_command,
)
from src.operator_api.runtime_config import OperatorRuntimeSettings


pytestmark = pytest.mark.integration


def test_runtime_entrypoint_exports_importable_app() -> None:
    assert isinstance(app, FastAPI)
    assert isinstance(create_runtime_app(), FastAPI)

    health = TestClient(app).get("/health").json()

    assert health["ok"] is True
    assert health["service"] == "content-automation-operator-api"
    assert health["auth_required"] is True


def test_runtime_start_command_uses_runtime_settings() -> None:
    settings = OperatorRuntimeSettings(api_host="0.0.0.0", api_port=8015, _env_file=None)

    command = runtime_start_command(settings)

    assert command == ["uvicorn", APP_IMPORT_PATH, "--host", "0.0.0.0", "--port", "8015"]


def test_runtime_metadata_is_safe_and_complete() -> None:
    settings = OperatorRuntimeSettings(api_host="127.0.0.1", api_port=8016, log_level="debug", demo_mode=True, _env_file=None)

    metadata = runtime_metadata(settings)

    assert metadata["ok"] is True
    assert metadata["kind"] == "runtime_entrypoint"
    assert metadata["app_import_path"] == APP_IMPORT_PATH
    assert metadata["factory_import_path"] == FACTORY_IMPORT_PATH
    assert metadata["start_command"] == ["uvicorn", APP_IMPORT_PATH, "--host", "127.0.0.1", "--port", "8016"]
    assert metadata["runtime"]["log_level"] == "DEBUG"
    assert metadata["runtime"]["demo_mode"] is True
