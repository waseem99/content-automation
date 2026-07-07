from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from src.infrastructure.database.connection import Database
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_app import create_app
from src.operator_api.runtime_config import OperatorRuntimeSettings, get_operator_runtime_settings


def create_configured_app(
    database: Database | None = None,
    auth_settings: OperatorAuthSettings | None = None,
    runtime_settings: OperatorRuntimeSettings | None = None,
) -> FastAPI:
    settings = runtime_settings or get_operator_runtime_settings()
    app = create_app(database=database, auth_settings=auth_settings)
    app.state.runtime_settings = settings

    @app.get("/runtime/config")
    def runtime_config() -> dict[str, Any]:
        return {"ok": True, "kind": "runtime_config", "runtime": settings.public_snapshot()}

    return app
