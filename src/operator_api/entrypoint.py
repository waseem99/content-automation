from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from src.operator_api.runtime_config import OperatorRuntimeSettings, get_operator_runtime_settings
from src.operator_api.runtime_factory import create_configured_app

APP_IMPORT_PATH = "src.operator_api.entrypoint:app"
FACTORY_IMPORT_PATH = "src.operator_api.entrypoint:create_runtime_app"


def create_runtime_app() -> FastAPI:
    return create_configured_app(runtime_settings=get_operator_runtime_settings())


app = create_runtime_app()


def runtime_start_command(settings: OperatorRuntimeSettings | None = None) -> list[str]:
    value = settings or get_operator_runtime_settings()
    return [
        "uvicorn",
        APP_IMPORT_PATH,
        "--host",
        value.api_host,
        "--port",
        str(value.api_port),
    ]


def runtime_metadata(settings: OperatorRuntimeSettings | None = None) -> dict[str, Any]:
    value = settings or get_operator_runtime_settings()
    return {
        "ok": True,
        "kind": "runtime_entrypoint",
        "app_import_path": APP_IMPORT_PATH,
        "factory_import_path": FACTORY_IMPORT_PATH,
        "start_command": runtime_start_command(value),
        "runtime": value.public_snapshot(),
    }
