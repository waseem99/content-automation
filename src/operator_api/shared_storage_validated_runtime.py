from __future__ import annotations

from fastapi import FastAPI

from src.application.shared_storage.runtime import SharedProviderRegistry
from src.application.shared_storage.validated_service import ValidatedSharedArtifactService
from src.infrastructure.database.connection import Database
from src.operator_api import shared_storage_runtime as base_runtime
from src.operator_api.auth import OperatorAuthSettings


def install_shared_storage_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    providers: SharedProviderRegistry | None = None,
) -> None:
    base_runtime.SharedArtifactService = ValidatedSharedArtifactService
    base_runtime.install_shared_storage_routes(
        app,
        database=database,
        auth_settings=auth_settings,
        providers=providers,
    )
