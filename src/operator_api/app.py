from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.application.p4_audit import P4AuditReportService
from src.application.p4_dashboard import P4DashboardContracts
from src.application.p4_demo_flow import P4DemoFlowService
from src.application.p4_surface import P4OperatorSurface
from src.application.portfolio_service import PortfolioService
from src.application.reference_intelligence_service import ReferenceIntelligenceService
from src.infrastructure.database.connection import Database
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class WorkflowRunRequest(BaseModel):
    topic: str
    source_urls: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    action: str
    resource_id: UUID
    rationale: str | None = None


class DemoApprovalRequest(BaseModel):
    rationale: str | None = None


class BrandRequest(BaseModel):
    slug: str
    display_name: str
    niche: str
    content_mode: str
    monthly_target: int = Field(ge=1, le=180)
    primary_platform: str = "facebook"
    source_links: list[str] = Field(default_factory=list)
    content_pillars: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioContentRequest(BaseModel):
    plan_id: UUID
    brand_slug: str
    scheduled_for: date
    title: str
    concept: str
    format_name: str


class PortfolioApprovalRequest(BaseModel):
    gate: str
    decision: str
    rationale: str


class PortfolioWorkspaceRequest(BaseModel):
    script: dict[str, Any] | None = None
    scene_plan: dict[str, Any] | None = None
    voiceover: dict[str, Any] | None = None
    premium_budget_usd: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class PortfolioArtifactRequest(BaseModel):
    kind: Literal["voiceover", "keyframe", "preview", "premium_clip", "thumbnail", "final_video", "package"]
    label: str = Field(min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1)
    local_locator: str = Field(pattern=r"^content://[A-Za-z0-9._/-]+$", max_length=500)
    mime_type: str = Field(min_length=3, max_length=120)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MonthPlanRequest(BaseModel):
    brand_id: UUID
    month_start: date
    target_count: int = Field(ge=1, le=180)
    strategy: dict[str, Any] = Field(default_factory=dict)


class PlatformPackageRequest(BaseModel):
    title: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    disclosure: dict[str, Any] = Field(default_factory=dict)


class PerformanceRequest(BaseModel):
    observed_at: datetime
    metrics: dict[str, Any]
    source: str = "manual"


class ReferenceSourceRequest(BaseModel):
    local_reference_id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    source_url: str | None = Field(default=None, max_length=2000)
    title: str = Field(min_length=1, max_length=300)
    platform: Literal[
        "facebook", "instagram", "youtube", "tiktok", "x", "snapchat",
        "google-drive", "local", "unknown",
    ]
    media_type: Literal["video", "image", "carousel", "mixed", "unknown"] = "unknown"
    rights_declaration: Literal[
        "owned", "permitted", "public-internal-research", "rights-holder-upload"
    ]
    limitations: list[str] = Field(default_factory=list, max_length=30)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceJobProgressRequest(BaseModel):
    status: Literal["queued", "running", "partial", "succeeded", "failed", "cancelled"]
    stage: Literal[
        "intake", "acquisition", "normalization", "frames", "transcript",
        "analysis", "temporal_report", "fingerprint", "comparison", "complete",
    ]
    progress_percent: int = Field(ge=0, le=100)
    worker_label: str | None = Field(default=None, max_length=120)
    error_code: str | None = Field(default=None, max_length=120)
    error: str | None = Field(default=None, max_length=2000)


class ReferenceArtifactRequest(BaseModel):
    job_id: UUID | None = None
    artifact_kind: Literal[
        "contact_sheet", "analysis_report", "temporal_report", "fingerprint",
        "comparison_report", "pattern_library", "pattern_brief", "originality_gate",
    ]
    version: int = Field(default=1, ge=1)
    local_locator: str = Field(max_length=500)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mime_type: str = Field(min_length=3, max_length=120)
    summary: dict[str, Any] = Field(default_factory=dict)
    contains_source_media: bool = False


class ReferenceBrandRequest(BaseModel):
    brand_id: UUID
    rationale: str | None = Field(default=None, max_length=1000)


class ReferenceGateRequest(BaseModel):
    gate: Literal["rights", "originality", "editorial"]
    decision: Literal["pending", "approved", "changes_requested", "rejected"]
    rationale: str = Field(min_length=10, max_length=2000)
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ResearchIdeaLinkRequest(BaseModel):
    portfolio_content_id: UUID
    relationship: Literal[
        "pattern_evidence", "topic_signal", "format_evidence", "risk_reference"
    ]
    pattern_ids: list[str] = Field(default_factory=list, max_length=50)
    transformation_note: str = Field(min_length=20, max_length=3000)


def create_app(database: Database | None = None, auth_settings: OperatorAuthSettings | None = None) -> FastAPI:
    app = FastAPI(title="Content Automation Operator API", version="0.7.0")
    app.state.database = database
    app.state.auth_settings = auth_settings or OperatorAuthSettings()
    require_operator = build_operator_auth(app.state.auth_settings)
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("OPERATOR_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Operator-Key"],
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        db = _database_or_none(app)
        auth = _auth_settings(app)
        return {
            "ok": True,
            "service": "content-automation-operator-api",
            "version": "0.7.0",
            "database_configured": db is not None,
            "auth_required": not auth.disabled,
        }

    @app.post("/workflows/{workflow_run_id}/run")
    def run_workflow(
        workflow_run_id: UUID,
        request: WorkflowRunRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return P4OperatorSurface(_database(app)).run_workflow(
            workflow_run_id=workflow_run_id,
            topic=request.topic,
            source_urls=tuple(request.source_urls),
            actor=operator.operator_id,
        )

    @app.get("/workflows/{workflow_run_id}/queue")
    def queue(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4OperatorSurface(_database(app)).queue(workflow_run_id=workflow_run_id)}

    @app.get("/workflows/{workflow_run_id}/dashboard/queue")
    def dashboard_queue(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DashboardContracts(_database(app)).queue_cards(workflow_run_id=workflow_run_id)}

    @app.get("/workflows/{workflow_run_id}/dashboard/schema")
    def dashboard_schema(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, "workflow_run_id": str(workflow_run_id), **P4DashboardContracts(_database(app)).schema()}

    @app.post("/workflows/{workflow_run_id}/approvals")
    def approval_action(
        workflow_run_id: UUID,
        request: ApprovalRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return P4DashboardContracts(_database(app)).approval_action(
            action=request.action,
            workflow_run_id=workflow_run_id,
            resource_id=request.resource_id,
            reviewed_by=operator.operator_id,
            rationale=request.rationale,
        )

    @app.get("/workflows/{workflow_run_id}/audit")
    def audit(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4AuditReportService(_database(app)).report(workflow_run_id=workflow_run_id)}

    @app.get("/demo/scenario")
    def demo_scenario(operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DemoFlowService(_database(app)).scenario()}

    @app.post("/demo/{workflow_run_id}/start")
    def demo_start(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).start(workflow_run_id=workflow_run_id)

    @app.post("/demo/{workflow_run_id}/approve-current")
    def demo_approve_current(
        workflow_run_id: UUID,
        request: DemoApprovalRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).approve_current(
            workflow_run_id=workflow_run_id,
            reviewed_by=operator.operator_id,
            rationale=request.rationale,
        )

    @app.get("/demo/{workflow_run_id}/status")
    def demo_status(
        workflow_run_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DemoFlowService(_database(app)).status(workflow_run_id=workflow_run_id)}

    @app.post("/portfolio/brands")
    def upsert_brand(
        request: BrandRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        brand = PortfolioService(_database(app)).create_brand(request.model_dump())
        return {"ok": True, "operator": operator.operator_id, "brand": brand}

    @app.get("/portfolio/brands")
    def list_brands(
        operator=Depends(require_operator),
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        brands = PortfolioService(_database(app)).list_brands(active_only=not include_inactive)
        return {"ok": True, "operator": operator.operator_id, "count": len(brands), "brands": brands}

    @app.get("/portfolio/queue")
    def portfolio_queue(
        operator=Depends(require_operator),
        brand_id: UUID | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        items = PortfolioService(_database(app)).queue(brand_id=brand_id, stage=stage)
        return {"ok": True, "operator": operator.operator_id, "count": len(items), "items": items}

    @app.get("/portfolio/readiness")
    def portfolio_readiness(
        month_start: date,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).month_readiness(month_start=month_start)
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/plans")
    def create_portfolio_plan(
        request: MonthPlanRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return PortfolioService(_database(app)).create_month_plan(
            **request.model_dump(), created_by=operator.operator_id
        )

    @app.post("/portfolio/content")
    def add_portfolio_content(
        request: PortfolioContentRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).add_content(**request.model_dump())
        return {"operator": operator.operator_id, **result}

    @app.get("/portfolio/content/{content_id}")
    def portfolio_content_detail(
        content_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return {"operator": operator.operator_id, **PortfolioService(_database(app)).detail(content_id)}

    @app.post("/portfolio/content/{content_id}/workspace")
    def update_portfolio_workspace(
        content_id: UUID,
        request: PortfolioWorkspaceRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).update_workspace(content_id=content_id, **request.model_dump())
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/content/{content_id}/artifacts")
    def register_portfolio_artifact(
        content_id: UUID,
        request: PortfolioArtifactRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).register_artifact(
            content_id=content_id, payload=request.model_dump(), created_by=operator.operator_id
        )
        return {"operator": operator.operator_id, **result}

    @app.get("/portfolio/content/{content_id}/artifacts/{artifact_id}/media")
    def portfolio_artifact_media(
        content_id: UUID,
        artifact_id: UUID,
        operator=Depends(require_operator),
    ) -> FileResponse:
        artifact = PortfolioService(_database(app)).artifact(content_id=content_id, artifact_id=artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="artifact_not_found")
        root = Path(os.getenv("PORTFOLIO_MEDIA_ROOT", "var/portfolio-media")).resolve()
        relative = str(artifact["local_locator"]).removeprefix("content://")
        media_path = (root / relative).resolve()
        if root not in media_path.parents or not media_path.is_file():
            raise HTTPException(status_code=404, detail="local_media_not_available")
        return FileResponse(media_path, media_type=str(artifact["mime_type"]), filename=media_path.name)

    @app.post("/portfolio/content/{content_id}/approvals")
    def approve_portfolio_gate(
        content_id: UUID,
        request: PortfolioApprovalRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        return PortfolioService(_database(app)).approve_gate(
            content_id=content_id,
            gate=request.gate,
            reviewer=operator.operator_id,
            rationale=request.rationale,
            decision=request.decision,
        )

    @app.post("/portfolio/content/{content_id}/packages")
    def create_platform_packages(
        content_id: UUID,
        request: PlatformPackageRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).create_platform_packages(content_id=content_id, **request.model_dump())
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/packages/{package_id}/metrics")
    def record_platform_metrics(
        package_id: UUID,
        request: PerformanceRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = PortfolioService(_database(app)).record_metrics(package_id=package_id, **request.model_dump())
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/references")
    def enqueue_reference(
        request: ReferenceSourceRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).enqueue_reference(
            request.model_dump(), created_by=operator.operator_id
        )
        return {"operator": operator.operator_id, **result}

    @app.get("/portfolio/references")
    def reference_queue(
        operator=Depends(require_operator),
        brand_id: UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        items = ReferenceIntelligenceService(_database(app)).queue(
            brand_id=brand_id, platform=platform, status=status
        )
        return {
            "ok": True,
            "operator": operator.operator_id,
            "count": len(items),
            "items": items,
            "processing_runtime": "operator-controlled-local-worker",
            "source_media_in_api": False,
            "automatic_publication": False,
        }

    @app.get("/portfolio/references/{source_id}")
    def reference_detail(
        source_id: UUID,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).detail(source_id)
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/reference-jobs/{job_id}/progress")
    def record_reference_progress(
        job_id: UUID,
        request: ReferenceJobProgressRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).record_job_progress(
            job_id, request.model_dump()
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/references/{source_id}/artifacts")
    def register_reference_artifact(
        source_id: UUID,
        request: ReferenceArtifactRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).register_artifact(
            source_id, request.model_dump()
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/references/{source_id}/brands")
    def assign_reference_brand(
        source_id: UUID,
        request: ReferenceBrandRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).assign_brand(
            source_id,
            brand_id=request.brand_id,
            assigned_by=operator.operator_id,
            rationale=request.rationale,
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/references/{source_id}/approvals")
    def decide_reference_gate(
        source_id: UUID,
        request: ReferenceGateRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).decide_gate(
            source_id, request.model_dump(), reviewer=operator.operator_id
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/portfolio/references/{source_id}/ideas")
    def link_reference_idea(
        source_id: UUID,
        request: ResearchIdeaLinkRequest,
        operator=Depends(require_operator),
    ) -> dict[str, Any]:
        result = ReferenceIntelligenceService(_database(app)).link_idea(
            source_id, request.model_dump(), created_by=operator.operator_id
        )
        return {"operator": operator.operator_id, **result}

    return app


def _auth_settings(app: FastAPI) -> OperatorAuthSettings:
    value = getattr(app.state, "auth_settings", None)
    return value if isinstance(value, OperatorAuthSettings) else OperatorAuthSettings()


def _database_or_none(app: FastAPI) -> Database | None:
    value = getattr(app.state, "database", None)
    return value if isinstance(value, Database) else None


def _database(app: FastAPI) -> Database:
    database = _database_or_none(app)
    if database is None:
        raise RuntimeError("operator API database is not configured")
    return database
