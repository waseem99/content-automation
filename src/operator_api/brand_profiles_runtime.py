from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.brand_profile_service import BrandProfileService
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class NarrationPresetRequest(BaseModel):
    preset_key: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["primary", "energetic", "serious"]
    approved_voice_id: UUID
    language: str = Field(min_length=2, max_length=20)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    style: dict[str, Any] = Field(default_factory=dict)
    pronunciation_rules: dict[str, Any] = Field(default_factory=dict)
    format_filters: list[str] = Field(default_factory=list, max_length=20)
    topic_filters: list[str] = Field(default_factory=list, max_length=30)
    is_default: bool = False


class BrandProfileDraftRequest(BaseModel):
    default_language: str = Field(min_length=2, max_length=20)
    audience: dict[str, Any] = Field(default_factory=dict)
    tone: str = Field(min_length=3, max_length=500)
    visual_rules: dict[str, Any] = Field(default_factory=dict)
    content_restrictions: dict[str, Any] = Field(default_factory=dict)
    cadence: dict[str, Any] = Field(default_factory=dict)
    platforms: list[str] = Field(min_length=1, max_length=20)
    budget: dict[str, Any] = Field(default_factory=dict)
    presets: list[NarrationPresetRequest] = Field(min_length=1, max_length=3)


class ContentNarrationSelectionRequest(BaseModel):
    preset_id: UUID


def install_brand_profile_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "brand_profile_routes_installed", False):
        return
    app.state.brand_profile_routes_installed = True
    service = BrandProfileService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> BrandProfileService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    @app.get("/portfolio/approved-voices")
    def list_approved_voices(
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        with require_database().connection() as conn:
            rows = conn.execute(
                """SELECT id, provider, provider_voice_id, display_name, voice_type,
                          allowed_languages, allowed_platforms, prohibited_uses, expires_at,
                          (consent_evidence_asset_id IS NOT NULL) AS has_consent_evidence
                   FROM football_brief.approved_voices
                   WHERE approval_status='approved'
                     AND (expires_at IS NULL OR expires_at > now())
                   ORDER BY provider, display_name"""
            ).fetchall()
        voices = [dict(row) for row in rows]
        return {"ok": True, "operator": operator.operator_id, "count": len(voices), "voices": voices}

    @app.get("/portfolio/brands/{brand_id}/profiles")
    def list_brand_profiles(
        brand_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
        profiles = require_service().list_profiles(brand_id)
        return {"ok": True, "operator": operator.operator_id, "count": len(profiles), "profiles": profiles}

    @app.post("/portfolio/brands/{brand_id}/profiles")
    def create_brand_profile(
        brand_id: UUID,
        request: BrandProfileDraftRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.MANAGE_BRANDS, brand_id=str(brand_id))
        try:
            result = require_service().create_draft(
                brand_id=brand_id,
                profile=request.model_dump(exclude={"presets"}),
                presets=[preset.model_dump() for preset in request.presets],
                actor=operator.operator_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/brands/{brand_id}/profiles/{profile_id}/activate")
    def activate_brand_profile(
        brand_id: UUID,
        profile_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.MANAGE_BRANDS, brand_id=str(brand_id))
        try:
            result = require_service().activate(
                brand_id=brand_id,
                profile_id=profile_id,
                actor=operator.operator_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"operator": operator.operator_id, **result}

    @app.get("/portfolio/brands/{brand_id}/narration-selection")
    def recommend_narration_preset(
        brand_id: UUID,
        language: str | None = Query(default=None, max_length=20),
        format_name: str | None = Query(default=None, max_length=80),
        topic_type: str | None = Query(default=None, max_length=120),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
        try:
            selection = require_service().select(
                brand_id=brand_id,
                language=language,
                format_name=format_name,
                topic_type=topic_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "operator": operator.operator_id, "selection": asdict(selection)}

    @app.post("/portfolio/content/{content_id}/narration-selection")
    def pin_content_narration_preset(
        content_id: UUID,
        request: ContentNarrationSelectionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        result = require_service().bind_content(content_id=content_id, preset_id=request.preset_id)
        return {"operator": operator.operator_id, **result}
