from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_studio_v2_media_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "studio_v2_media_routes_installed", False):
        return
    app.state.studio_v2_media_routes_installed = True
    access = OperatorAccessService(database) if database is not None else None
    artifact_root = Path(os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")).resolve()

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    @app.get("/studio-v2/jobs/{job_id}/media", include_in_schema=False)
    def local_job_media(
        job_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> FileResponse:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT gj.status,gj.output_payload,mp.brand_id
                   FROM football_brief.generation_jobs gj
                   JOIN football_brief.portfolio_content pc ON pc.id=gj.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE gj.id=%s""",
                (job_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="generation_job_not_found")
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(row["brand_id"]))
        if row["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="generation_job_not_succeeded")
        output = dict(row["output_payload"] or {})
        candidate = Path(str(output.get("storage_path") or "")).resolve()
        if not candidate.is_file() or (candidate != artifact_root and artifact_root not in candidate.parents):
            raise HTTPException(status_code=404, detail="local_job_media_unavailable")
        expected_mime = str(output.get("mime_type") or "").strip()
        guessed_mime = mimetypes.guess_type(candidate.name)[0]
        media_type = expected_mime or guessed_mime or "application/octet-stream"
        if not media_type.startswith(("audio/", "image/", "video/")):
            raise HTTPException(status_code=415, detail="unsupported_local_media_type")
        response = FileResponse(candidate, media_type=media_type, filename=candidate.name)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


__all__ = ["install_studio_v2_media_routes"]
