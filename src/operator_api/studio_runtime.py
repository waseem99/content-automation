from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


STUDIO_ROOT = Path(__file__).resolve().parents[2] / "web" / "static-creator-ui"


def install_studio_routes(app: FastAPI, *, studio_root: Path | None = None) -> None:
    if getattr(app.state, "production_studio_routes_installed", False):
        return
    app.state.production_studio_routes_installed = True
    root = (studio_root or STUDIO_ROOT).resolve()
    index = root / "index.html"
    if not index.is_file():
        app.state.production_studio_available = False
        return

    assets = root / "assets"
    data = root / "data"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="studio-assets")
    if data.is_dir():
        app.mount("/data", StaticFiles(directory=data), name="studio-data")

    def studio_response() -> FileResponse:
        response = FileResponse(index, media_type="text/html")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/", include_in_schema=False)
    def studio_index() -> FileResponse:
        return studio_response()

    @app.get("/app", include_in_schema=False)
    @app.get("/studio", include_in_schema=False)
    def studio_alias() -> FileResponse:
        return studio_response()

    @app.get("/studio/status")
    def studio_status() -> dict[str, Any]:
        if not index.is_file():
            raise HTTPException(status_code=503, detail="production_studio_unavailable")
        return {
            "ok": True,
            "kind": "production_creator_studio",
            "same_origin_api": True,
            "authentication": "operator_key",
            "demo_fallback": False,
        }

    app.state.production_studio_available = True


__all__ = ["STUDIO_ROOT", "install_studio_routes"]
