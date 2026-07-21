from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI

from src.infrastructure.database.connection import Database
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings, get_operator_runtime_settings
from src.operator_api.runtime_factory import create_configured_app

APP_IMPORT_PATH = "src.operator_api.entrypoint:app"
FACTORY_IMPORT_PATH = "src.operator_api.entrypoint:create_runtime_app"


def create_runtime_app() -> FastAPI:
    settings = get_operator_runtime_settings()
    database = _open_runtime_database(settings)
    application = create_configured_app(
        database=database,
        auth_settings=_operator_auth_from_environment(),
        runtime_settings=settings,
    )
    if database is not None:
        @application.on_event("shutdown")
        def close_runtime_database() -> None:
            database.close()
    return application


def _open_runtime_database(settings: OperatorRuntimeSettings) -> Database | None:
    if not settings.auto_connect_database:
        return None
    database = Database(settings.database_settings())
    database.open(require_schema=settings.database_require_schema)
    return database


def _operator_auth_from_environment() -> OperatorAuthSettings:
    raw = os.getenv("OPERATOR_API_KEYS_JSON", "").strip()
    if not raw:
        return OperatorAuthSettings()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OPERATOR_API_KEYS_JSON must be valid JSON") from exc
    if not isinstance(value, dict) or not value or not all(
        isinstance(key, str) and key.strip() and isinstance(operator, str) and operator.strip()
        for key, operator in value.items()
    ):
        raise RuntimeError("OPERATOR_API_KEYS_JSON must map non-empty keys to operator IDs")
    return OperatorAuthSettings(api_keys=value, resolve_identities_from_database=True)


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
