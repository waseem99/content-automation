from __future__ import annotations

from fastapi import FastAPI

from src.application.releases.audio_bound_service import AudioBoundFinalReleaseService
from src.infrastructure.database.connection import Database
from src.operator_api import releases_runtime as base_runtime
from src.operator_api.auth import OperatorAuthSettings


def install_release_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    base_runtime.ValidatedFinalReleaseService = AudioBoundFinalReleaseService
    base_runtime.install_release_routes(
        app,
        database=database,
        auth_settings=auth_settings,
    )
