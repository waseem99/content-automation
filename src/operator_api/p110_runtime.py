from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.portfolio_service import PortfolioService
from src.application.production_workflow_service import ProductionWorkflowError, ProductionWorkflowService
from src.application.scripts.models import ScriptAdapterMode, ScriptDecision, ScriptGenerateRequest
from src.application.scripts.service import ScriptReviewService
from src.infrastructure.database.connection import Database
from src.operations.job_logging import ObservedGenerationJobService as GenerationJobService
from src.operations.local_pipeline import _seed
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth
from src.operator_api.studio_v2_runtime import (
    StudioCreateContentRequest,
    StudioStartProductionRequest,
    StudioV2Service,
)


ALL_PLATFORMS = ("facebook", "instagram", "tiktok", "youtube", "youtube_shorts")
SHORT_FORM_PLATFORMS = ("facebook", "instagram", "tiktok", "youtube_shorts")
PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "facebook": {
        "label": "Facebook video",
        "aspect_ratio": "4:5",
        "dimensions": "1080x1350",
        "placement": "feed_video",
        "caption_treatment": "burned-in captions plus post copy",
    },
    "instagram": {
        "label": "Instagram video",
        "aspect_ratio": "4:5",
        "dimensions": "1080x1350",
        "placement": "feed_video",
        "caption_treatment": "safe-area captions plus post copy",
    },
    "tiktok": {
        "label": "TikTok",
        "aspect_ratio": "9:16",
        "dimensions": "1080x1920",
        "placement": "vertical_video",
        "caption_treatment": "large safe-area captions",
    },
    "youtube": {
        "label": "YouTube video",
        "aspect_ratio": "16:9",
        "dimensions": "1920x1080",
        "placement": "standard_video",
        "caption_treatment": "subtitle track plus optional burned-in captions",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "aspect_ratio": "9:16",
        "dimensions": "1080x1920",
        "placement": "shorts",
        "caption_treatment": "large safe-area captions",
    },
}


class P110Error(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


class P110CreateContentRequest(BaseModel):
    brand_id: UUID
    title: str = Field(min_length=3, max_length=240)
    topic: str = Field(min_length=3, max_length=3000)
    objective: str = Field(default="", max_length=2000)
    audience: str = Field(default="", max_length=1000)
    platform: str = Field(default="facebook", min_length=2, max_length=80)
    primary_platform: str = Field(default="facebook", min_length=2, max_length=80)
    target_platforms: list[str] = Field(default_factory=list, max_length=10)
    format_name: str = Field(default="master_video", min_length=2, max_length=80)
    duration_seconds: int = Field(default=120, ge=10, le=150)
    short_cut_count: int = Field(default=0, ge=0, le=2)
    language: str = Field(default="en-US", min_length=2, max_length=40)
    scheduled_for: date
    notes: str = Field(default="", max_length=5000)
    generate_script: bool = True
    starting_point: Literal["manual_topic", "suggestion", "approved_plan"] = "manual_topic"

    @model_validator(mode="after")
    def normalize_platform_selection(self) -> "P110CreateContentRequest":
        requested = self.platform.strip().lower()
        primary = self.primary_platform.strip().lower()
        if requested not in {*ALL_PLATFORMS, "all"}:
            raise ValueError("platform must be facebook, instagram, tiktok, youtube, youtube_shorts, or all")
        if primary not in ALL_PLATFORMS:
            raise ValueError("primary_platform is not supported")
        selected = [str(value).strip().lower() for value in self.target_platforms if str(value).strip()]
        if requested == "all":
            selected = list(ALL_PLATFORMS) if not selected else selected
        elif not selected:
            selected = [requested]
        selected = list(dict.fromkeys(selected))
        if any(value not in ALL_PLATFORMS for value in selected):
            raise ValueError("target_platforms contains an unsupported platform")
        if primary not in selected:
            selected.insert(0, primary)
        self.platform = requested
        self.primary_platform = primary
        self.target_platforms = selected
        if self.duration_seconds < 90 and self.format_name == "master_video":
            self.format_name = "vertical_short" if primary in {"tiktok", "youtube_shorts"} else "explainer"
        return self


class ResearchClaimRequest(BaseModel):
    claim_id: UUID
    query: str | None = Field(default=None, max_length=2000)
    limit: int = Field(default=5, ge=1, le=8)


class ManualSourceRequest(BaseModel):
    claim_id: UUID
    url: str = Field(min_length=12, max_length=4000)
    title: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, max_length=500)
    source_type: str = Field(default="secondary")


class AttachSourceRequest(BaseModel):
    candidate_id: UUID
    claim_ids: list[UUID] = Field(min_length=1, max_length=20)
    expected_lock_version: int = Field(ge=0)
    support_type: Literal["direct", "corroborating", "contextual", "limitation"] = "corroborating"
    support_note: str = Field(default="Supports the selected factual claim.", min_length=3, max_length=5000)
    locator: str | None = Field(default=None, max_length=1000)


class RejectCandidateRequest(BaseModel):
    reason: str = Field(default="Not suitable for this claim.", min_length=3, max_length=1000)


class ReviewPolicyRequest(BaseModel):
    policy_key: Literal[
        "independent_review_required",
        "admin_self_review_allowed",
        "independent_final_release_required",
    ]
    rationale_required_for_override: bool = False


class P110DecisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    decision: ScriptDecision
    rationale: str = Field(default="", max_length=5000)


class WikipediaResearchAdapter:
    endpoint = "https://en.wikipedia.org/w/api.php"
    user_agent = "ContentAutomationP110/1.0 (operator-controlled source research)"

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        params = urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srnamespace": 0,
                "format": "json",
                "utf8": 1,
            }
        )
        request = Request(f"{self.endpoint}?{params}", headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed official HTTPS host
            payload = json.loads(response.read(512_000).decode("utf-8"))
        rows = payload.get("query", {}).get("search", [])
        output: list[dict[str, Any]] = []
        for index, row in enumerate(rows[:limit], start=1):
            title = str(row.get("title") or "").strip()
            snippet = _plain_text(str(row.get("snippet") or ""))
            if len(title) < 3 or not snippet:
                continue
            canonical_url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            evidence = f"{title}\n{snippet}\n{canonical_url}"
            output.append(
                {
                    "rank": index,
                    "title": title,
                    "publisher": "Wikipedia",
                    "canonical_url": canonical_url,
                    "published_on": None,
                    "source_type": "secondary",
                    "quality_score": Decimal("70.00"),
                    "relevance_summary": snippet[:1500],
                    "evidence_locator": f"Wikipedia search result for {title}",
                    "evidence_digest": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
                    "rights_declaration": "publicly_accessible",
                    "permitted_use": "Use for factual verification and citation; do not reproduce article text or media verbatim.",
                    "metadata": {"pageid": row.get("pageid"), "wordcount": row.get("wordcount")},
                }
            )
        return output


class P110Service:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.studio = StudioV2Service(database)
        configured_worker = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer")
        if configured_worker == "local-producer":
            configured_worker = os.getenv("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer")
        self.worker_id = configured_worker
        self.studio.worker_id = configured_worker
        self.portfolio = PortfolioService(database)
        self.workflows = ProductionWorkflowService(database)
        self.jobs = GenerationJobService(database)
        self.scripts = ScriptReviewService(database)
        self.ollama_endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.wikipedia = WikipediaResearchAdapter()

    def create_content(self, request: P110CreateContentRequest, *, actor: str) -> dict[str, Any]:
        base = StudioCreateContentRequest(
            brand_id=request.brand_id,
            title=request.title,
            topic=request.topic,
            objective=request.objective,
            audience=request.audience,
            platform=request.primary_platform,
            format_name=request.format_name,
            duration_seconds=request.duration_seconds,
            language=request.language,
            scheduled_for=request.scheduled_for,
            notes=request.notes,
            generate_script=False,
            starting_point=request.starting_point,
        )
        created = self.studio.create_content(base, actor=actor)
        content_id = UUID(str(created["content_id"]))
        with self.database.transaction() as conn:
            master = conn.execute(
                """UPDATE football_brief.portfolio_content
                   SET primary_platform=%s,target_platforms=%s::text[],target_duration_seconds=%s,
                       format=%s,
                       adaptation_profile=%s::jsonb,
                       metadata=metadata || %s::jsonb
                   WHERE id=%s
                   RETURNING *""",
                (
                    request.primary_platform,
                    request.target_platforms,
                    request.duration_seconds,
                    request.format_name,
                    json.dumps(PLATFORM_PROFILES[request.primary_platform]),
                    json.dumps(
                        {
                            "p110": {
                                "platform_mode": request.platform,
                                "primary_platform": request.primary_platform,
                                "target_platforms": request.target_platforms,
                                "target_duration_seconds": request.duration_seconds,
                                "short_cut_count": request.short_cut_count,
                                "master_first": True,
                            }
                        }
                    ),
                    content_id,
                ),
            ).fetchone()
            if master is None:
                raise P110Error("content_not_found")
            derivatives = self._create_derivative_plans(conn, master=dict(master), request=request, actor=actor)
        script_job = self.enqueue_script(content_id=content_id, actor=actor) if request.generate_script else None
        return {
            "ok": True,
            "kind": "p110_content_family_created",
            "content_id": str(content_id),
            "workflow_id": str(created["workflow_id"]),
            "script_job": script_job,
            "derivatives_created": len(derivatives),
            "family": self.family(content_id),
            "state": self.studio.content_state(content_id),
        }

    def _create_derivative_plans(
        self,
        conn: Any,
        *,
        master: dict[str, Any],
        request: P110CreateContentRequest,
        actor: str,
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        family_id = master["id"]
        for platform in request.target_platforms:
            if platform == request.primary_platform:
                continue
            existing = conn.execute(
                """SELECT * FROM football_brief.portfolio_content
                   WHERE content_family_id=%s AND variant_type='adaptation' AND primary_platform=%s""",
                (family_id, platform),
            ).fetchone()
            if existing:
                created.append(dict(existing))
                continue
            profile = PLATFORM_PROFILES[platform]
            concept = (
                f"Adapt the approved {request.primary_platform} master for {profile['label']}. "
                "Preserve the approved factual claims, sources, narrative meaning and brand voice. "
                f"Reframe only for {profile['aspect_ratio']} and the {profile['placement']} placement."
            )
            fingerprint = hashlib.sha256(f"{family_id}:adaptation:{platform}:v1".encode()).hexdigest()
            row = conn.execute(
                """INSERT INTO football_brief.portfolio_content
                   (plan_id,scheduled_for,title,concept,format,stage,concept_fingerprint,semantic_key,
                    version,brand_profile_id,narration_preset_id,metadata,content_family_id,parent_content_id,
                    variant_type,primary_platform,target_platforms,target_duration_seconds,adaptation_profile)
                   VALUES (%s,%s,%s,%s,'adaptation','idea',%s,%s,1,%s,%s,%s::jsonb,%s,%s,
                           'adaptation',%s,ARRAY[%s]::text[],%s,%s::jsonb)
                   RETURNING *""",
                (
                    master["plan_id"],
                    master["scheduled_for"],
                    f"{master['title']} — {profile['label']}",
                    concept,
                    fingerprint,
                    f"p110-{family_id}-adaptation-{platform}",
                    master.get("brand_profile_id"),
                    master.get("narration_preset_id"),
                    json.dumps({"p110_derivative": True, "created_by": actor, "master_content_id": str(family_id)}),
                    family_id,
                    family_id,
                    platform,
                    platform,
                    request.duration_seconds,
                    json.dumps(profile),
                ),
            ).fetchone()
            created.append(dict(row))

        cut_duration = min(60, max(15, request.duration_seconds // max(request.short_cut_count, 1)))
        for index in range(1, request.short_cut_count + 1):
            existing = conn.execute(
                """SELECT * FROM football_brief.portfolio_content
                   WHERE content_family_id=%s AND variant_type='short_cut' AND short_cut_index=%s""",
                (family_id, index),
            ).fetchone()
            if existing:
                created.append(dict(existing))
                continue
            concept = (
                f"Create short cut {index} from one complete narrative beat of the approved master. "
                "Use only master claims and source-backed meaning; write a distinct hook and a complete ending. "
                "The cut is intended for Facebook Reels, Instagram Reels, TikTok and YouTube Shorts."
            )
            fingerprint = hashlib.sha256(f"{family_id}:short-cut:{index}:v1".encode()).hexdigest()
            profile = {
                "label": f"Short cut {index}",
                "aspect_ratio": "9:16",
                "dimensions": "1080x1920",
                "placement": "reels_shorts_tiktok",
                "caption_treatment": "large safe-area captions",
                "source_strategy": "complete narrative beat from approved master",
            }
            row = conn.execute(
                """INSERT INTO football_brief.portfolio_content
                   (plan_id,scheduled_for,title,concept,format,stage,concept_fingerprint,semantic_key,
                    version,brand_profile_id,narration_preset_id,metadata,content_family_id,parent_content_id,
                    variant_type,primary_platform,target_platforms,target_duration_seconds,short_cut_index,
                    adaptation_profile)
                   VALUES (%s,%s,%s,%s,'short_cut','idea',%s,%s,1,%s,%s,%s::jsonb,%s,%s,
                           'short_cut','tiktok',%s::text[],%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    master["plan_id"],
                    master["scheduled_for"],
                    f"{master['title']} — Short cut {index}",
                    concept,
                    fingerprint,
                    f"p110-{family_id}-short-cut-{index}",
                    master.get("brand_profile_id"),
                    master.get("narration_preset_id"),
                    json.dumps({"p110_derivative": True, "created_by": actor, "master_content_id": str(family_id)}),
                    family_id,
                    family_id,
                    list(SHORT_FORM_PLATFORMS),
                    cut_duration,
                    index,
                    json.dumps(profile),
                ),
            ).fetchone()
            created.append(dict(row))
        return created

    def family(self, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            seed = conn.execute(
                "SELECT content_family_id FROM football_brief.portfolio_content WHERE id=%s",
                (content_id,),
            ).fetchone()
            if seed is None:
                raise P110Error("content_not_found")
            rows = conn.execute(
                """SELECT pc.*,b.id AS brand_id,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE pc.content_family_id=%s
                   ORDER BY CASE pc.variant_type WHEN 'master' THEN 0 WHEN 'adaptation' THEN 1 ELSE 2 END,
                            pc.primary_platform,pc.short_cut_index,pc.id""",
                (seed["content_family_id"],),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                state = self.studio.content_state(UUID(str(item["id"])))
                item["workflow_status"] = state["status"]
                item["workflow_status_label"] = state["status_label"]
                item["next_actions"] = state["next_actions"]
                item["blockers"] = state["blockers"]
            except Exception as exc:  # family inventory must remain visible for an incomplete derivative
                item["workflow_status"] = "planned"
                item["workflow_status_label"] = "Planned"
                item["next_actions"] = [{"action": "generate_script", "label": "Generate adaptation script"}]
                item["blockers"] = [{"code": "state_pending", "message": str(exc)}]
            items.append(item)
        return {
            "ok": True,
            "kind": "p110_content_family",
            "content_family_id": str(seed["content_family_id"]),
            "items": items,
            "platform_profiles": PLATFORM_PROFILES,
        }

    def enqueue_script(self, *, content_id: UUID, actor: str) -> dict[str, Any]:
        try:
            workflow = self.workflows.workflow_for_content(content_id=content_id)
        except ProductionWorkflowError as exc:
            if exc.code != "workflow_not_found":
                raise
            created = self.workflows.initialize(content_id=content_id, actor=actor)
            workflow = self.workflows.detail(workflow_id=UUID(str(created["workflow_id"])))
        workflow_id = UUID(str(workflow["workflow"]["id"]))
        if str(workflow["workflow"]["current_stage"]) == "concept_draft":
            item = self.portfolio.detail(content_id)
            content = item.get("item", {})
            self.studio._accept_manual_brief(
                workflow_id=workflow_id,
                actor=actor,
                brief={
                    "starting_point": "p110_content_family",
                    "topic": content.get("concept"),
                    "platform": content.get("primary_platform"),
                    "target_platforms": content.get("target_platforms") or [],
                    "duration_seconds": content.get("target_duration_seconds"),
                    "variant_type": content.get("variant_type"),
                    "parent_content_id": str(content.get("parent_content_id") or "") or None,
                },
            )

        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id,pc.version,pc.format,pc.primary_platform,pc.target_duration_seconds,
                          pc.variant_type,pc.parent_content_id,pw.id AS workflow_id,
                          pw.current_version_id AS workflow_version_id,bp.default_language
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   JOIN football_brief.production_workflow_versions pwv ON pwv.id=pw.current_version_id
                   JOIN football_brief.brand_profiles bp
                     ON bp.id=COALESCE(pc.brand_profile_id,NULLIF(pwv.snapshot->>'brand_profile_id','')::uuid)
                   LEFT JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                   WHERE pc.id=%s AND pw.status='active' AND pw.current_stage='script_draft'
                     AND sd.id IS NULL""",
                (content_id,),
            ).fetchone()
        if row is None:
            state = self.studio.content_state(content_id)
            active = [
                job for job in state["jobs"]
                if job["job_type"] == "script" and job["status"] in {"queued", "running", "succeeded"}
            ]
            if active:
                return {"ok": True, "reused": True, "job": active[0]}
            raise P110Error("script_not_queueable", details={"blockers": state.get("blockers", [])})

        script_request = ScriptGenerateRequest(
            platform=row["primary_platform"] or "facebook",
            format=row["format"] or "master_video",
            language=row["default_language"] or "en-US",
            target_duration_seconds=float(row["target_duration_seconds"] or 45),
            words_per_minute=float(os.getenv("LOCAL_SCRIPT_WORDS_PER_MINUTE", "150")),
            duration_tolerance_percent=10,
            seed=_seed(row["id"], row["version"], self.ollama_model),
            adapter_mode=ScriptAdapterMode.LOCAL_MODEL,
            local_endpoint=self.ollama_endpoint,
            local_model_id=self.ollama_model,
            local_timeout_seconds=int(os.getenv("LOCAL_SCRIPT_TIMEOUT_SECONDS", "180")),
        )
        job_request = GenerationJobEnqueue(
            portfolio_content_id=row["id"],
            content_version=int(row["version"]),
            production_workflow_id=row["workflow_id"],
            production_workflow_version_id=row["workflow_version_id"],
            job_type=GenerationJobType.SCRIPT,
            provider="ollama-local",
            model_id=self.ollama_model,
            preferred_worker_id=self.worker_id,
            priority=50,
            idempotency_key=(
                f"p110-script:{row['id']}:v{row['version']}:{row['primary_platform']}:"
                f"{row['target_duration_seconds']}:{self.ollama_model}"
            ),
            input_payload={"request": script_request.model_dump(mode="json")},
            timeout_seconds=max(script_request.local_timeout_seconds + 30, 60),
            max_attempts=3,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
            legacy_source={
                "local_pipeline": True,
                "studio_v2": True,
                "p110": True,
                "variant_type": row["variant_type"],
                "parent_content_id": str(row["parent_content_id"]) if row["parent_content_id"] else None,
            },
        )
        try:
            job = self.jobs.enqueue(job_request, actor=actor)
        except GenerationJobError as exc:
            raise P110Error(exc.code, details=exc.details) from exc
        return {"ok": True, "reused": bool(job.get("reused")), "job": job}

    def review_policy(self, brand_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT p.*,b.display_name AS brand_name,b.slug AS brand_slug
                   FROM football_brief.brand_review_policies p
                   JOIN football_brief.brands b ON b.id=p.brand_id
                   WHERE p.brand_id=%s AND p.active=true
                   ORDER BY p.version DESC LIMIT 1""",
                (brand_id,),
            ).fetchone()
        if row is None:
            raise P110Error("brand_review_policy_not_found")
        return {"ok": True, "kind": "p110_review_policy", "policy": dict(row)}

    def set_review_policy(self, brand_id: UUID, request: ReviewPolicyRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            brand = conn.execute("SELECT id FROM football_brief.brands WHERE id=%s AND active=true", (brand_id,)).fetchone()
            if brand is None:
                raise P110Error("brand_not_found")
            current = conn.execute(
                """SELECT * FROM football_brief.brand_review_policies
                   WHERE brand_id=%s AND active=true ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (brand_id,),
            ).fetchone()
            if (
                current
                and current["policy_key"] == request.policy_key
                and bool(current["rationale_required_for_override"]) == request.rationale_required_for_override
            ):
                return {"ok": True, "reused": True, "policy": dict(current)}
            version = conn.execute(
                "SELECT COALESCE(max(version),0)+1 AS value FROM football_brief.brand_review_policies WHERE brand_id=%s",
                (brand_id,),
            ).fetchone()["value"]
            if current:
                conn.execute("UPDATE football_brief.brand_review_policies SET active=false WHERE id=%s", (current["id"],))
            row = conn.execute(
                """INSERT INTO football_brief.brand_review_policies
                   (brand_id,version,policy_key,active,rationale_required_for_override,
                    created_by,activated_at,metadata)
                   VALUES (%s,%s,%s,true,%s,%s,now(),%s::jsonb)
                   RETURNING *""",
                (
                    brand_id,
                    version,
                    request.policy_key,
                    request.rationale_required_for_override,
                    actor,
                    json.dumps({"changed_in_creator_studio": True}),
                ),
            ).fetchone()
        return {"ok": True, "reused": False, "policy": dict(row)}

    def decide_script(
        self,
        *,
        document_id: UUID,
        request: P110DecisionRequest,
        actor: OperatorIdentity,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT sd.id,sd.current_version_id,sd.lock_version,sv.status,sv.last_edited_by,
                          mp.brand_id,p.policy_key,p.rationale_required_for_override
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   LEFT JOIN football_brief.brand_review_policies p ON p.brand_id=mp.brand_id AND p.active=true
                   WHERE sd.id=%s FOR UPDATE OF sd,sv""",
                (document_id,),
            ).fetchone()
            if row is None:
                raise P110Error("script_document_not_found")
            if int(row["lock_version"]) != request.expected_lock_version:
                raise P110Error(
                    "script_document_conflict",
                    details={"expected": request.expected_lock_version, "current": int(row["lock_version"])},
                )
            if row["status"] != "in_review":
                raise P110Error("script_version_not_in_review")
            policy = str(row["policy_key"] or "independent_review_required")
            same_actor = str(row["last_edited_by"]) == actor.operator_id
            self_review = bool(same_actor and actor.is_admin)
            if same_actor and not actor.is_admin:
                raise P110Error("independent_script_review_required")
            if same_actor and policy == "independent_review_required":
                raise P110Error("brand_policy_requires_independent_review")
            rationale = request.rationale.strip()
            if not rationale:
                rationale = {
                    ScriptDecision.APPROVED: "Approved",
                    ScriptDecision.CHANGES_REQUESTED: "Changes requested",
                    ScriptDecision.REJECTED: "Rejected",
                }[request.decision]
            if self_review and bool(row["rationale_required_for_override"]) and len(rationale) < 3:
                raise P110Error("admin_override_rationale_required")
            conn.execute(
                """INSERT INTO football_brief.script_review_decisions
                   (script_document_id,script_version_id,decision,reviewer_operator_id,rationale,
                    document_lock_version,self_review,review_policy_key,override_reason)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    document_id,
                    row["current_version_id"],
                    request.decision.value,
                    actor.operator_id,
                    rationale,
                    request.expected_lock_version,
                    self_review,
                    policy,
                    f"Same-session Admin progression under {policy}" if self_review else None,
                ),
            )
            conn.execute(
                "UPDATE football_brief.script_versions SET status=%s,decided_at=now() WHERE id=%s",
                (request.decision.value, row["current_version_id"]),
            )
            updated = conn.execute(
                """UPDATE football_brief.script_documents
                   SET lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s RETURNING id""",
                (document_id, request.expected_lock_version),
            ).fetchone()
            if updated is None:
                raise P110Error("script_document_conflict")
        return {
            "ok": True,
            "kind": "p110_script_decision",
            "self_review": self_review,
            "review_policy_key": policy,
            **self.scripts.detail(document_id=document_id),
        }

    def research_claim(
        self,
        *,
        document_id: UUID,
        request: ResearchClaimRequest,
        actor: str,
    ) -> dict[str, Any]:
        context = self._claim_context(document_id=document_id, claim_id=request.claim_id)
        query = (request.query or "").strip() or f"{context['claim_text']} {context['brand_name']}"
        with self.database.transaction() as conn:
            run = conn.execute(
                """INSERT INTO football_brief.script_source_research_runs
                   (script_document_id,script_version_id,claim_id,query,provider,provider_model,status,requested_by,
                    retrieval_evidence)
                   VALUES (%s,%s,%s,%s,'wikipedia','mediawiki-search-v1','running',%s,%s::jsonb)
                   RETURNING *""",
                (
                    document_id,
                    context["script_version_id"],
                    request.claim_id,
                    query,
                    actor,
                    json.dumps({"operator_triggered": True, "claim_key": context["claim_key"]}),
                ),
            ).fetchone()
        try:
            candidates = self.wikipedia.search(query, limit=request.limit)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            with self.database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.script_source_research_runs
                       SET status='failed',error_code=%s,completed_at=now(),
                           retrieval_evidence=retrieval_evidence || %s::jsonb
                       WHERE id=%s""",
                    (
                        type(exc).__name__.lower(),
                        json.dumps({"error": str(exc)[:500]}),
                        run["id"],
                    ),
                )
            raise P110Error("source_research_provider_failed", details={"message": str(exc)}) from exc
        with self.database.transaction() as conn:
            inserted: list[dict[str, Any]] = []
            for candidate in candidates:
                row = conn.execute(
                    """INSERT INTO football_brief.script_source_research_candidates
                       (research_run_id,rank,title,publisher,canonical_url,published_on,source_type,
                        quality_score,relevance_summary,evidence_locator,evidence_digest,rights_declaration,
                        permitted_use,metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                       ON CONFLICT (research_run_id,canonical_url) DO NOTHING
                       RETURNING *""",
                    (
                        run["id"],
                        candidate["rank"],
                        candidate["title"],
                        candidate["publisher"],
                        candidate["canonical_url"],
                        candidate["published_on"],
                        candidate["source_type"],
                        candidate["quality_score"],
                        candidate["relevance_summary"],
                        candidate["evidence_locator"],
                        candidate["evidence_digest"],
                        candidate["rights_declaration"],
                        candidate["permitted_use"],
                        json.dumps(candidate["metadata"]),
                    ),
                ).fetchone()
                if row:
                    inserted.append(dict(row))
            status = "completed" if inserted else "no_results"
            conn.execute(
                """UPDATE football_brief.script_source_research_runs
                   SET status=%s,result_count=%s,completed_at=now(),
                       retrieval_evidence=retrieval_evidence || %s::jsonb
                   WHERE id=%s""",
                (
                    status,
                    len(inserted),
                    json.dumps({"retrieved_candidates": len(inserted), "provider_host": "en.wikipedia.org"}),
                    run["id"],
                ),
            )
        return {"ok": True, "kind": "p110_source_research", "run_id": str(run["id"]), "status": status, "candidates": inserted}

    def manual_source_candidate(
        self,
        *,
        document_id: UUID,
        request: ManualSourceRequest,
        actor: str,
    ) -> dict[str, Any]:
        context = self._claim_context(document_id=document_id, claim_id=request.claim_id)
        inspected = _inspect_public_url(request.url)
        title = (request.title or inspected.get("title") or inspected["host"]).strip()
        publisher = (request.publisher or inspected["host"]).strip()
        if request.source_type not in {"primary", "government", "academic", "secondary", "news", "expert", "internal_reference"}:
            raise P110Error("unsupported_source_type")
        digest_payload = f"{title}\n{inspected['final_url']}\n{inspected.get('summary','')}"
        with self.database.transaction() as conn:
            run = conn.execute(
                """INSERT INTO football_brief.script_source_research_runs
                   (script_document_id,script_version_id,claim_id,query,provider,status,result_count,
                    requested_by,completed_at,retrieval_evidence)
                   VALUES (%s,%s,%s,%s,'manual_url','completed',1,%s,now(),%s::jsonb)
                   RETURNING *""",
                (
                    document_id,
                    context["script_version_id"],
                    request.claim_id,
                    inspected["final_url"],
                    actor,
                    json.dumps({"operator_triggered": True, "validated_host": inspected["host"]}),
                ),
            ).fetchone()
            candidate = conn.execute(
                """INSERT INTO football_brief.script_source_research_candidates
                   (research_run_id,rank,title,publisher,canonical_url,source_type,quality_score,
                    relevance_summary,evidence_locator,evidence_digest,rights_declaration,permitted_use,
                    validation_status,validated_at,metadata)
                   VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'publicly_accessible',%s,'valid',now(),%s::jsonb)
                   RETURNING *""",
                (
                    run["id"],
                    title,
                    publisher,
                    inspected["final_url"],
                    request.source_type,
                    _quality_score_for_host(inspected["host"], request.source_type),
                    inspected.get("summary") or f"Operator supplied and validated source from {inspected['host']}",
                    inspected.get("title") or title,
                    hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
                    "Use for factual verification and citation; respect the source site's copyright and media rights.",
                    json.dumps({"content_type": inspected.get("content_type"), "manual": True}),
                ),
            ).fetchone()
        return {"ok": True, "kind": "p110_manual_source_candidate", "run_id": str(run["id"]), "candidate": dict(candidate)}

    def research_for_document(self, document_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            runs = conn.execute(
                """SELECT r.*,c.claim_key,c.claim_text
                   FROM football_brief.script_source_research_runs r
                   JOIN football_brief.script_claims c ON c.id=r.claim_id
                   WHERE r.script_document_id=%s
                   ORDER BY r.requested_at DESC,r.id DESC LIMIT 50""",
                (document_id,),
            ).fetchall()
            run_ids = [row["id"] for row in runs]
            candidates = [] if not run_ids else conn.execute(
                """SELECT * FROM football_brief.script_source_research_candidates
                   WHERE research_run_id = ANY(%s::uuid[])
                   ORDER BY created_at DESC,rank""",
                (run_ids,),
            ).fetchall()
        return {
            "ok": True,
            "kind": "p110_source_research_history",
            "runs": [dict(row) for row in runs],
            "candidates": [dict(row) for row in candidates],
            "provider": {"key": "wikipedia", "label": "Wikipedia web research", "operator_triggered": True},
        }

    def attach_source(
        self,
        *,
        document_id: UUID,
        request: AttachSourceRequest,
        actor: str,
    ) -> dict[str, Any]:
        inspected_candidate: dict[str, Any]
        with self.database.connection() as conn:
            candidate = conn.execute(
                """SELECT c.*,r.script_document_id,r.script_version_id
                   FROM football_brief.script_source_research_candidates c
                   JOIN football_brief.script_source_research_runs r ON r.id=c.research_run_id
                   WHERE c.id=%s AND r.script_document_id=%s""",
                (request.candidate_id, document_id),
            ).fetchone()
        if candidate is None:
            raise P110Error("research_candidate_not_found")
        inspected_candidate = _inspect_public_url(str(candidate["canonical_url"]))
        with self.database.transaction() as conn:
            doc = conn.execute(
                """SELECT sd.current_version_id,sd.lock_version,sv.status
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   WHERE sd.id=%s FOR UPDATE OF sd,sv""",
                (document_id,),
            ).fetchone()
            if doc is None:
                raise P110Error("script_document_not_found")
            if int(doc["lock_version"]) != request.expected_lock_version:
                raise P110Error(
                    "script_document_conflict",
                    details={"expected": request.expected_lock_version, "current": int(doc["lock_version"])},
                )
            if doc["status"] != "working":
                raise P110Error("working_script_revision_required_for_sources")
            if str(candidate["script_version_id"]) != str(doc["current_version_id"]):
                raise P110Error("research_candidate_is_for_stale_script_version")
            claims = conn.execute(
                """SELECT * FROM football_brief.script_claims
                   WHERE script_version_id=%s AND id = ANY(%s::uuid[]) FOR UPDATE""",
                (doc["current_version_id"], request.claim_ids),
            ).fetchall()
            if len(claims) != len(set(request.claim_ids)):
                raise P110Error("one_or_more_claims_not_found")
            source = conn.execute(
                """SELECT * FROM football_brief.script_sources
                   WHERE script_version_id=%s AND canonical_url=%s""",
                (doc["current_version_id"], inspected_candidate["final_url"]),
            ).fetchone()
            if source is None:
                source_key = f"web-{str(candidate['id']).replace('-', '')[:12]}"
                source = conn.execute(
                    """INSERT INTO football_brief.script_sources
                       (script_version_id,source_key,source_type,title,publisher,canonical_url,published_on,
                        quality_score,rights_declaration,permitted_use,evidence_digest,notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING *""",
                    (
                        doc["current_version_id"],
                        source_key,
                        candidate["source_type"],
                        candidate["title"],
                        candidate["publisher"],
                        inspected_candidate["final_url"],
                        candidate["published_on"],
                        candidate["quality_score"],
                        candidate["rights_declaration"],
                        candidate["permitted_use"],
                        candidate["evidence_digest"],
                        candidate["relevance_summary"],
                    ),
                ).fetchone()
            for claim in claims:
                conn.execute(
                    """INSERT INTO football_brief.script_claim_sources
                       (script_version_id,claim_id,source_id,support_type,locator,support_note)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (claim_id,source_id,support_type) DO UPDATE SET
                         locator=EXCLUDED.locator,support_note=EXCLUDED.support_note""",
                    (
                        doc["current_version_id"],
                        claim["id"],
                        source["id"],
                        request.support_type,
                        request.locator or candidate["evidence_locator"],
                        request.support_note,
                    ),
                )
                if claim["claim_type"] == "factual" and request.support_type in {"direct", "corroborating"}:
                    conn.execute(
                        "UPDATE football_brief.script_claims SET support_status='supported' WHERE id=%s",
                        (claim["id"],),
                    )
            conn.execute(
                """UPDATE football_brief.script_source_research_candidates
                   SET validation_status='valid',validated_at=now(),accepted_by=%s,accepted_at=now(),
                       metadata=metadata || %s::jsonb
                   WHERE id=%s""",
                (
                    actor,
                    json.dumps({"validated_final_url": inspected_candidate["final_url"]}),
                    candidate["id"],
                ),
            )
            updated = conn.execute(
                """UPDATE football_brief.script_documents
                   SET lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s RETURNING id""",
                (document_id, request.expected_lock_version),
            ).fetchone()
            if updated is None:
                raise P110Error("script_document_conflict")
        return {
            "ok": True,
            "kind": "p110_source_attached",
            "source_id": str(source["id"]),
            "claim_ids": [str(value) for value in request.claim_ids],
            **self.scripts.detail(document_id=document_id),
        }

    def reject_candidate(self, *, candidate_id: UUID, request: RejectCandidateRequest, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """UPDATE football_brief.script_source_research_candidates
                   SET rejected_by=%s,rejected_at=now(),metadata=metadata || %s::jsonb
                   WHERE id=%s AND accepted_at IS NULL RETURNING *""",
                (actor, json.dumps({"rejection_reason": request.reason}), candidate_id),
            ).fetchone()
        if row is None:
            raise P110Error("research_candidate_not_found_or_already_accepted")
        return {"ok": True, "kind": "p110_source_candidate_rejected", "candidate": dict(row)}

    def _claim_context(self, *, document_id: UUID, claim_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT sd.current_version_id AS script_version_id,sv.status,sc.id AS claim_id,
                          sc.claim_key,sc.claim_text,sc.claim_type,sc.support_status,
                          b.id AS brand_id,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.script_claims sc ON sc.script_version_id=sv.id
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE sd.id=%s AND sc.id=%s""",
                (document_id, claim_id),
            ).fetchone()
        if row is None:
            raise P110Error("script_claim_not_found")
        return dict(row)


def _plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _assert_public_https_url(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise P110Error("source_url_must_be_public_https")
    if parsed.username or parsed.password:
        raise P110Error("source_url_credentials_are_not_allowed")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise P110Error("private_source_host_not_allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise P110Error("source_host_could_not_be_resolved", details={"host": host}) from exc
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise P110Error("private_source_host_not_allowed", details={"host": host})
    return value.strip(), host


def _inspect_public_url(value: str) -> dict[str, Any]:
    safe_url, _ = _assert_public_https_url(value)
    request = Request(
        safe_url,
        headers={
            "User-Agent": "ContentAutomationP110/1.0 (operator-selected source validation)",
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - URL passed strict public HTTPS/SSRF validation
            final_url = response.geturl()
            _, final_host = _assert_public_https_url(final_url)
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            raw = response.read(512_000)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise P110Error("source_url_validation_failed", details={"message": str(exc)}) from exc
    text = raw.decode("utf-8", errors="replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    description_match = re.search(
        r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"'](.*?)[\"']",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    title = _plain_text(title_match.group(1))[:1000] if title_match else None
    summary = _plain_text(description_match.group(1))[:1500] if description_match else None
    return {
        "final_url": final_url,
        "host": final_host,
        "content_type": content_type,
        "title": title,
        "summary": summary,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _quality_score_for_host(host: str, source_type: str) -> Decimal:
    if source_type in {"government", "academic", "primary"}:
        return Decimal("90.00")
    if host.endswith((".gov", ".gov.uk", ".edu", ".ac.uk")):
        return Decimal("90.00")
    if source_type in {"news", "expert"}:
        return Decimal("78.00")
    return Decimal("70.00")


def install_p110_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p110_routes_installed", False):
        return
    app.state.p110_routes_installed = True
    service = P110Service(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> P110Service:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def content_brand_id(content_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def document_brand_id(document_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.script_documents sd
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE sd.id=%s""",
                (document_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="script_document_not_found")
        return str(row["brand_id"])

    @app.get("/p110/platform-profiles")
    def platform_profiles(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {
            "ok": True,
            "kind": "p110_platform_profiles",
            "platforms": PLATFORM_PROFILES,
            "duration": {"minimum_seconds": 10, "maximum_seconds": 150, "presets": [15, 30, 45, 60, 90, 120, 150]},
            "short_cut_count": {"minimum": 0, "maximum": 2},
        }

    @app.post("/p110/content")
    def create_content(
        request: P110CreateContentRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=str(request.brand_id))
        try:
            result = require_service().create_content(request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p110/content/{content_id}/family")
    def content_family(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=content_brand_id(content_id))
        try:
            result = require_service().family(content_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/content/{content_id}/generate-script")
    def generate_script(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand_id(content_id))
        try:
            result = require_service().enqueue_script(content_id=content_id, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result, "state": require_service().studio.content_state(content_id)}

    @app.post("/p110/content/{content_id}/start-local-production")
    def start_local_production(
        content_id: UUID,
        request: StudioStartProductionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand_id(content_id))
        return {
            "operator": operator.operator_id,
            **require_service().studio.start_local_production(
                content_id=content_id,
                actor=operator.operator_id,
                include_audio=request.include_audio,
                include_visuals=request.include_visuals,
            ),
        }

    @app.get("/p110/brands/{brand_id}/review-policy")
    def get_review_policy(
        brand_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
        try:
            result = require_service().review_policy(brand_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/brands/{brand_id}/review-policy")
    def set_review_policy(
        brand_id: UUID,
        request: ReviewPolicyRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        try:
            result = require_service().set_review_policy(brand_id, request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/scripts/{document_id}/decisions")
    def decide_script(
        document_id: UUID,
        request: P110DecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=document_brand_id(document_id))
        try:
            result = require_service().decide_script(document_id=document_id, request=request, actor=operator)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p110/scripts/{document_id}/research")
    def research_history(
        document_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=document_brand_id(document_id))
        return {"operator": operator.operator_id, **require_service().research_for_document(document_id)}

    @app.post("/p110/scripts/{document_id}/research")
    def research_claim(
        document_id: UUID,
        request: ResearchClaimRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=document_brand_id(document_id))
        try:
            result = require_service().research_claim(document_id=document_id, request=request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/scripts/{document_id}/manual-source")
    def manual_source(
        document_id: UUID,
        request: ManualSourceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=document_brand_id(document_id))
        try:
            result = require_service().manual_source_candidate(document_id=document_id, request=request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/scripts/{document_id}/sources/attach")
    def attach_source(
        document_id: UUID,
        request: AttachSourceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=document_brand_id(document_id))
        try:
            result = require_service().attach_source(document_id=document_id, request=request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p110/research/candidates/{candidate_id}/reject")
    def reject_candidate(
        candidate_id: UUID,
        request: RejectCandidateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().reject_candidate(candidate_id=candidate_id, request=request, actor=operator.operator_id)
        except P110Error as exc:
            raise_p110_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_p110_error(exc: P110Error) -> None:
    if exc.code in {"content_not_found", "brand_not_found", "script_document_not_found", "script_claim_not_found", "research_candidate_not_found"}:
        status_code = 404
    elif exc.code in {
        "script_document_conflict",
        "research_candidate_is_for_stale_script_version",
        "brand_policy_requires_independent_review",
        "independent_script_review_required",
        "script_version_not_in_review",
        "working_script_revision_required_for_sources",
    }:
        status_code = 409
    elif exc.code in {"source_research_provider_failed", "source_url_validation_failed"}:
        status_code = 502
    elif exc.code in {"private_source_host_not_allowed", "source_url_credentials_are_not_allowed"}:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = [
    "P110CreateContentRequest",
    "P110Service",
    "PLATFORM_PROFILES",
    "install_p110_routes",
]
