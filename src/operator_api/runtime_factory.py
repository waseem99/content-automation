from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.infrastructure.database.connection import Database
from src.operator_api.access_runtime import install_operator_access
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.brand_profiles_runtime import install_brand_profile_routes
from src.operator_api.generation_jobs_runtime import install_generation_job_routes
from src.operator_api.observability import observability_contract
from src.operator_api.app import create_app
from src.operator_api.production_workflow_runtime import install_production_workflow_routes
from src.operator_api.runtime_config import OperatorRuntimeSettings, get_operator_runtime_settings


def create_configured_app(
    database: Database | None = None,
    auth_settings: OperatorAuthSettings | None = None,
    runtime_settings: OperatorRuntimeSettings | None = None,
) -> FastAPI:
    settings = runtime_settings or get_operator_runtime_settings()
    auth = auth_settings or OperatorAuthSettings()
    app = create_app(database=database, auth_settings=auth)
    install_operator_access(app, database=database, auth_settings=auth)
    install_brand_profile_routes(app, database=database, auth_settings=auth)
    install_production_workflow_routes(app, database=database, auth_settings=auth)
    install_generation_job_routes(app, database=database, auth_settings=auth)
    app.state.runtime_settings = settings

    @app.get("/runtime/config")
    def runtime_config() -> dict[str, Any]:
        return {"ok": True, "kind": "runtime_config", "runtime": settings.public_snapshot()}

    @app.get("/runtime/ready", response_model=None)
    def runtime_ready() -> Any:
        payload = _runtime_readiness_payload(database=database, settings=settings)
        if payload["ok"]:
            return payload
        return JSONResponse(status_code=503, content=payload)

    @app.get("/runtime/observability")
    def runtime_observability() -> dict[str, Any]:
        return observability_contract()

    return app


def _runtime_readiness_payload(*, database: Database | None, settings: OperatorRuntimeSettings) -> dict[str, Any]:
    if database is None:
        return {
            "ok": False,
            "kind": "runtime_readiness",
            "checks": {
                "runtime_configured": True,
                "database_configured": False,
                "database_reachable": False,
                "schema_required": settings.database_require_schema,
                "schema_ready": False,
                "migrations_ready": False,
            },
            "runtime": settings.public_snapshot(),
        }

    health = database.health_check(settings.database_migrations_dir)
    schema_ready = health.schema_present and health.migrations_table_present
    migrations_ready = not health.expected_migrations or set(health.expected_migrations).issubset(health.applied_migrations)
    ok = health.database_reachable and (not settings.database_require_schema or (schema_ready and migrations_ready))

    return {
        "ok": ok,
        "kind": "runtime_readiness",
        "checks": {
            "runtime_configured": True,
            "database_configured": True,
            "database_reachable": health.database_reachable,
            "schema_required": settings.database_require_schema,
            "schema_ready": schema_ready,
            "migrations_ready": migrations_ready,
        },
        "runtime": settings.public_snapshot(),
    }
