from __future__ import annotations

from fastapi import FastAPI

from src.application.shared_storage.audited_service import AuditedSharedArtifactService
from src.application.shared_storage.runtime import SharedProviderRegistry
from src.infrastructure.database.connection import Database
from src.operator_api import shared_storage_runtime as base_runtime
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.shared_storage_management_runtime import install_shared_storage_management_routes


def install_shared_storage_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    providers: SharedProviderRegistry | None = None,
) -> None:
    registry = providers or SharedProviderRegistry()
    base_runtime.SharedArtifactService = AuditedSharedArtifactService
    base_runtime.install_shared_storage_routes(
        app,
        database=database,
        auth_settings=auth_settings,
        providers=registry,
    )
    install_shared_storage_management_routes(
        app,
        database=database,
        auth_settings=auth_settings,
        providers=registry,
    )
