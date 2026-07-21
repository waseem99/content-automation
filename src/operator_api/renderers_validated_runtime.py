from __future__ import annotations

from fastapi import FastAPI

from src.application.renderers.validated_service import ValidatedRendererCatalogueService
from src.infrastructure.database.connection import Database
from src.operator_api import renderers_runtime as base_runtime
from src.operator_api.auth import OperatorAuthSettings


def install_renderer_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    """Install the existing scoped routes using the validated catalogue service."""

    base_runtime.RendererCatalogueService = ValidatedRendererCatalogueService
    base_runtime.install_renderer_routes(
        app,
        database=database,
        auth_settings=auth_settings,
    )
