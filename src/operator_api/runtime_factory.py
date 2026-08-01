from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.application.scripts.runtime_patch import install_validated_script_service
from src.infrastructure.database.connection import Database
from src.operations.settings import OperationsSettings, get_operations_settings
from src.operator_api.acceptance_bootstrap_runtime import install_acceptance_bootstrap_routes
from src.operator_api.acceptance_candidates_runtime import install_acceptance_candidate_routes
from src.operator_api.acceptance_controlled_snapshot_runtime import (
    install_acceptance_controlled_snapshot_routes,
)
from src.operator_api.acceptance_controlled_start_runtime import (
    install_acceptance_controlled_start_routes,
)
from src.operator_api.acceptance_readiness_runtime import install_acceptance_readiness_routes
from src.operator_api.acceptance_validated_runtime import install_acceptance_routes
from src.operator_api.access_runtime import install_operator_access
from src.operator_api.audio_runtime import install_audio_routes
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.brand_profiles_runtime import install_brand_profile_routes
from src.operator_api.concepts_runtime import install_concept_routes
from src.operator_api.delivery_runtime import install_delivery_routes
from src.operator_api.generation_jobs_runtime import install_generation_job_routes
from src.operator_api.observability import observability_contract
from src.operator_api.app import create_app
from src.operator_api.operations_middleware import OperationsSafetyMiddleware
from src.operator_api.operations_validated_runtime import install_operations_routes
from src.operator_api.p110_runtime import install_p110_routes
from src.operator_api.p111_runtime_patch import install_p111_super_admin_override_patch
from src.operator_api.p119_campaign_runtime import install_p119_campaign_routes
from src.operator_api.p120_pre_generation_runtime import install_p120_pre_generation_routes
from src.operator_api.p120_storage_runtime import install_p120_storage_routes
from src.operator_api.p121_campaign_grid_runtime import install_p121_campaign_grid_routes
from src.operator_api.p126_hybrid_routing_runtime import install_p126_hybrid_routing_routes
from src.operator_api.performance_runtime import install_performance_routes
from src.operator_api.production_workflow_runtime import install_production_workflow_routes
from src.operator_api.releases_validated_runtime import install_release_routes
from src.operator_api.renderers_validated_runtime import install_renderer_routes
from src.operator_api.review_workspace_runtime import install_review_workspace_routes
from src.operator_api.routing_runtime import install_routing_routes
from src.operator_api.routing_workspace_runtime import install_routing_workspace_routes
from src.operator_api.runtime_config import OperatorRuntimeSettings, get_operator_runtime_settings
from src.operator_api.scripts_runtime import install_script_routes
from src.operator_api.video_pilot_runtime import install_video_pilot_routes
from src.operator_api.visuals_runtime import install_visual_routes


install_validated_script_service()
install_p111_super_admin_override_patch()


def create_configured_app(
    database: Database | None = None,
    auth_settings: OperatorAuthSettings | None = None,
    runtime_settings: OperatorRuntimeSettings | None = None,
    operations_settings: OperationsSettings | None = None,
) -> FastAPI:
    settings = runtime_settings or get_operator_runtime_settings()
    operations = operations_settings or get_operations_settings()
    route_operations = operations
    if "/" not in operations.migration_head and "\\" not in operations.migration_head:
        route_operations = operations.model_copy(
            update={"migration_head": str(operations.migrations_dir / operations.migration_head)}
        )
    auth = auth_settings or OperatorAuthSettings()
    app = create_app(database=database, auth_settings=auth)
    app.add_middleware(OperationsSafetyMiddleware, settings=operations)
    install_operator_access(app, database=database, auth_settings=auth)
    install_brand_profile_routes(app, database=database, auth_settings=auth)
    install_production_workflow_routes(app, database=database, auth_settings=auth)
    install_generation_job_routes(app, database=database, auth_settings=auth)
    install_concept_routes(app, database=database, auth_settings=auth)
    install_script_routes(app, database=database, auth_settings=auth)
    install_p110_routes(app, database=database, auth_settings=auth)
    install_p119_campaign_routes(app, database=database, auth_settings=auth)
    install_p120_pre_generation_routes(app, database=database, auth_settings=auth)
    install_p120_storage_routes(app, database=database, auth_settings=auth)
    install_p121_campaign_grid_routes(app, database=database, auth_settings=auth)
    install_p126_hybrid_routing_routes(app, database=database, auth_settings=auth)
    install_audio_routes(app, database=database, auth_settings=auth)
    install_visual_routes(app, database=database, auth_settings=auth)
    install_review_workspace_routes(app, database=database, auth_settings=auth)
    install_renderer_routes(app, database=database, auth_settings=auth)
    install_routing_routes(app, database=database, auth_settings=auth)
    install_routing_workspace_routes(app, database=database, auth_settings=auth)
    install_release_routes(app, database=database, auth_settings=auth)
    install_delivery_routes(app, database=database, auth_settings=auth)
    install_performance_routes(app, database=database, auth_settings=auth)
    install_video_pilot_routes(app, database=database, auth_settings=auth)
    install_operations_routes(
        app,
        database=database,
        auth_settings=auth,
        operations_settings=route_operations,
    )
    install_acceptance_routes(app, database=database, auth_settings=auth)
    install_acceptance_readiness_routes(app, database=database, auth_settings=auth)
    install_acceptance_candidate_routes(app, database=database, auth_settings=auth)
    install_acceptance_bootstrap_routes(app, database=database, auth_settings=auth)
    install_acceptance_controlled_start_routes(
        app,
        database=database,
        auth_settings=auth,
    )
    install_acceptance_controlled_snapshot_routes(
        app,
        database=database,
        auth_settings=auth,
    )
    app.state.runtime_settings = settings
    app.state.operations_settings = operations

    @app.get("/runtime/config")
    def runtime_config() -> dict[str, Any]:
        return {
            "ok": True,
            "kind": "runtime_config",
            "runtime": settings.public_snapshot(),
            "operations": operations.public_snapshot(),
        }

    @app.get("/runtime/ready", response_model=None)
    def runtime_ready() -> Any:
        payload = _runtime_readiness_payload(database=database, settings=settings)
        payload["release"] = {
            "environment": operations.environment,
            "release_key": operations.release_key,
            "git_sha": operations.git_sha,
            "image_digest": operations.image_digest,
            "configuration_digest": operations.configuration_digest,
            "migration_head": operations.migration_head,
        }
        if payload["ok"]:
            return payload
        return JSONResponse(status_code=503, content=payload)

    @app.get("/runtime/observability")
    def runtime_observability() -> dict[str, Any]:
        return {
            **observability_contract(),
            "operations": {
                "structured_logs": operations.structured_logs,
                "request_ids": True,
                "worker_job_ids": True,
                "rate_limit": {
                    "requests_per_minute": operations.requests_per_minute,
                    "scope": "per_instance_client_hash",
                },
                "max_request_body_bytes": operations.max_request_body_bytes,
            },
        }

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
