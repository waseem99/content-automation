from __future__ import annotations

from fastapi import FastAPI

from src.application.acceptance.validated_service import ValidatedAcceptancePilotService
from src.infrastructure.database.connection import Database
from src.operator_api import acceptance_runtime as base_runtime
from src.operator_api.acceptance_revision_runtime import install_acceptance_revision_routes
from src.operator_api.auth import OperatorAuthSettings


def install_acceptance_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    base_runtime.AcceptancePilotService = ValidatedAcceptancePilotService
    base_runtime.install_acceptance_routes(
        app,
        database=database,
        auth_settings=auth_settings,
    )
    install_acceptance_revision_routes(
        app,
        database=database,
        auth_settings=auth_settings,
    )
