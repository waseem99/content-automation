from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService, canonical_fingerprint
from src.application.renderers.models import (
    RendererCapabilityRequest,
    RendererEntryRequest,
    RendererHealthRequest,
    RendererRepriceRequest,
    RendererStatus,
    SimulatedJobRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class RendererCatalogueError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


class RendererCatalogueService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.jobs = GenerationJobService(database)

    def create_entry(self, *, request: RendererEntryRequest, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            version = 1
            if request.parent_entry_id is not None:
                parent = conn.execute(
                    "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s FOR UPDATE",
                    (request.parent_entry_id,),
                ).fetchone()
                if not parent:
                    raise RendererCatalogueError("renderer_parent_not_found")
                if (
                    parent["provider_key"] != request.provider_key
                    or parent["model_key"] != request.model_key
                    or parent["operation"] != request.operation.value
                ):
                    raise RendererCatalogueError("renderer_parent_identity_mismatch")
                version = int(parent["version"]) + 1
            else:
                existing = conn.execute(
                    """SELECT 1 FROM football_brief.renderer_catalogue_entries
                       WHERE provider_key=%s AND model_key=%s AND operation=%s""",
                    (request.provider_key, request.model_key, request.operation.value),
                ).fetchone()
                if existing:
                    raise RendererCatalogueError("renderer_parent_required")

            health = "healthy" if request.adapter_kind.value == "simulated" else "unknown"
            row = conn.execute(
                """INSERT INTO football_brief.renderer_catalogue_entries
                   (provider_key,provider_display_name,model_key,model_display_name,operation,
                    version,parent_entry_id,adapter_kind,status,health_status,supported_formats,
                    min_duration_seconds,max_duration_seconds,duration_step_seconds,
                    supported_resolutions,capabilities,expected_latency_seconds,pricing,
                    pricing_currency,quality_rating,commercial_use_allowed,usage_terms_url,
                    usage_evidence_digest,usage_evidence_recorded_at,data_handling,notes,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                   RETURNING *""",
                (
                    request.provider_key,
                    request.provider_display_name,
                    request.model_key,
                    request.model_display_name,
                    request.operation.value,
                    version,
                    request.parent_entry_id,
                    request.adapter_kind.value,
                    health,
                    list(request.supported_formats),
                    request.min_duration_seconds,
                    request.max_duration_seconds,
                    request.duration_step_seconds,
                    _json(request.supported_resolutions),
                    _json(request.capabilities),
                    _json(request.expected_latency_seconds),
                    _json(request.pricing),
                    request.pricing_currency,
                    request.quality_rating,
                    request.commercial_use_allowed,
                    request.usage_terms_url,
                    request.usage_evidence_digest,
                    request.usage_evidence_recorded_at,
                    _json(request.data_handling),
                    request.notes,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "entry": dict(row)}

    def activate(self, *, entry_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s FOR UPDATE",
                (entry_id,),
            ).fetchone()
            if not row:
                raise RendererCatalogueError("renderer_entry_not_found")
            if row["status"] != RendererStatus.DRAFT.value:
                raise RendererCatalogueError("renderer_entry_not_draft")
            active = conn.execute(
                """SELECT id FROM football_brief.renderer_catalogue_entries
                   WHERE provider_key=%s AND model_key=%s AND operation=%s AND status='active'
                   FOR UPDATE""",
                (row["provider_key"], row["model_key"], row["operation"]),
            ).fetchone()
            if active:
                conn.execute(
                    """UPDATE football_brief.renderer_catalogue_entries
                       SET status='retired',retired_by=%s,retired_at=now()
                       WHERE id=%s""",
                    (actor, active["id"]),
                )
            activated = conn.execute(
                """UPDATE football_brief.renderer_catalogue_entries
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, entry_id),
            ).fetchone()
        return {"ok": True, "entry": dict(activated)}

    def retire(self, *, entry_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s FOR UPDATE",
                (entry_id,),
            ).fetchone()
            if not row:
                raise RendererCatalogueError("renderer_entry_not_found")
            if row["status"] != RendererStatus.ACTIVE.value:
                raise RendererCatalogueError("renderer_entry_not_active")
            retired = conn.execute(
                """UPDATE football_brief.renderer_catalogue_entries
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, entry_id),
            ).fetchone()
        return {"ok": True, "entry": dict(retired)}

    def reprice(
        self,
        *,
        entry_id: UUID,
        request: RendererRepriceRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            parent = conn.execute(
                "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s",
                (entry_id,),
            ).fetchone()
        if not parent:
            raise RendererCatalogueError("renderer_entry_not_found")
        if parent["status"] != RendererStatus.ACTIVE.value:
            raise RendererCatalogueError("renderer_entry_not_active")
        payload = RendererEntryRequest(
            provider_key=parent["provider_key"],
            provider_display_name=parent["provider_display_name"],
            model_key=parent["model_key"],
            model_display_name=parent["model_display_name"],
            operation=parent["operation"],
            adapter_kind=parent["adapter_kind"],
            supported_formats=tuple(parent["supported_formats"]),
            min_duration_seconds=parent["min_duration_seconds"],
            max_duration_seconds=parent["max_duration_seconds"],
            duration_step_seconds=parent["duration_step_seconds"],
            supported_resolutions=tuple(parent["supported_resolutions"]),
            capabilities=dict(parent["capabilities"] or {}),
            expected_latency_seconds=(
                request.expected_latency_seconds
                if request.expected_latency_seconds is not None
                else dict(parent["expected_latency_seconds"] or {})
            ),
            pricing=request.pricing,
            pricing_currency=parent["pricing_currency"],
            quality_rating=(request.quality_rating if request.quality_rating is not None else parent["quality_rating"]),
            commercial_use_allowed=parent["commercial_use_allowed"],
            usage_terms_url=parent["usage_terms_url"],
            usage_evidence_digest=request.usage_evidence_digest or parent["usage_evidence_digest"],
            usage_evidence_recorded_at=(
                request.usage_evidence_recorded_at or parent["usage_evidence_recorded_at"]
            ),
            data_handling=dict(parent["data_handling"] or {}),
            notes=f"{parent['notes'] or ''}\nRepriced: {request.rationale}".strip(),
            parent_entry_id=entry_id,
        )
        created = self.create_entry(request=payload, actor=actor)
        new_id = created["entry"]["id"]
        if request.activate:
            return self.activate(entry_id=new_id, actor=actor)
        return created

    def observe_health(
        self,
        *,
        entry_id: UUID,
        request: RendererHealthRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            entry = conn.execute(
                "SELECT id FROM football_brief.renderer_catalogue_entries WHERE id=%s",
                (entry_id,),
            ).fetchone()
            if not entry:
                raise RendererCatalogueError("renderer_entry_not_found")
            observation = conn.execute(
                """INSERT INTO football_brief.renderer_health_observations
                   (renderer_catalogue_entry_id,status,latency_ms,checked_by,details)
                   VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (entry_id, request.status.value, request.latency_ms, request.checked_by, _json(request.details)),
            ).fetchone()
        return {"ok": True, "observation": dict(observation), "entry": self.detail(entry_id=entry_id)["entry"]}

    def list_entries(
        self,
        *,
        statuses: Iterable[str] = (),
        operations: Iterable[str] = (),
        provider_key: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["true"]
        values: list[Any] = []
        normalized_statuses = list(statuses)
        normalized_operations = list(operations)
        if normalized_statuses:
            conditions.append("status=ANY(%s::text[])")
            values.append(normalized_statuses)
        if normalized_operations:
            conditions.append("operation=ANY(%s::text[])")
            values.append(normalized_operations)
        if provider_key:
            conditions.append("provider_key=%s")
            values.append(provider_key)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT * FROM football_brief.renderer_catalogue_entries
                    WHERE {' AND '.join(conditions)}
                    ORDER BY provider_display_name,model_display_name,operation,version DESC""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def detail(self, *, entry_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            entry = conn.execute(
                "SELECT * FROM football_brief.renderer_catalogue_entries WHERE id=%s",
                (entry_id,),
            ).fetchone()
            if not entry:
                raise RendererCatalogueError("renderer_entry_not_found")
            health = conn.execute(
                """SELECT * FROM football_brief.renderer_health_observations
                   WHERE renderer_catalogue_entry_id=%s ORDER BY observed_at DESC,id DESC""",
                (entry_id,),
            ).fetchall()
            preflights = conn.execute(
                """SELECT * FROM football_brief.renderer_preflight_records
                   WHERE renderer_catalogue_entry_id=%s ORDER BY created_at DESC LIMIT 100""",
                (entry_id,),
            ).fetchall()
        return {
            "ok": True,
            "entry": dict(entry),
            "health_observations": [dict(row) for row in health],
            "preflights": [dict(row) for row in preflights],
        }

    def preflight(self, *, request: RendererCapabilityRequest, actor: str) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_active_operator(conn, actor)
            content = conn.execute(
                """SELECT pc.id,pc.version,mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (request.portfolio_content_id,),
            ).fetchone()
            if not content:
                raise RendererCatalogueError("content_not_found")
            if int(content["version"]) != request.content_version:
                raise RendererCatalogueError(
                    "content_version_conflict",
                    details={"requested": request.content_version, "current": int(content["version"])},
                )
            conditions = ["status='active'", "operation=%s"]
            values: list[Any] = [request.operation.value]
            if request.renderer_catalogue_entry_id:
                conditions.append("id=%s")
                values.append(request.renderer_catalogue_entry_id)
            if request.provider_key:
                conditions.append("provider_key=%s")
                values.append(request.provider_key)
            if request.model_key:
                conditions.append("model_key=%s")
                values.append(request.model_key)
            entries = conn.execute(
                f"""SELECT * FROM football_brief.renderer_catalogue_entries
                    WHERE {' AND '.join(conditions)}
                    ORDER BY quality_rating DESC,provider_key,model_key,version DESC""",
                tuple(values),
            ).fetchall()

        request_payload = request.model_dump(mode="json")
        evaluated: list[tuple[dict[str, Any], list[str], Decimal, int | None]] = []
        for raw in entries:
            entry = dict(raw)
            reasons = self._rejection_reasons(entry, request)
            estimated = self._estimate_cost(entry, request)
            expected = self._expected_seconds(entry, request)
            evaluated.append((entry, reasons, estimated, expected))

        if evaluated:
            evaluated.sort(
                key=lambda item: (
                    bool(item[1]),
                    len(item[1]),
                    -float(item[0]["quality_rating"]),
                    float(item[2]),
                    item[0]["provider_key"],
                    item[0]["model_key"],
                )
            )
            entry, reasons, estimated, expected = evaluated[0]
        else:
            entry, reasons, estimated, expected = None, ["no_active_renderer"], Decimal("0"), None

        accepted = not reasons
        evidence_payload = {
            "request": request_payload,
            "renderer_catalogue_entry_id": str(entry["id"]) if entry else None,
        }
        fingerprint = canonical_fingerprint(evidence_payload)
        external_fee_possible = bool(entry and entry["adapter_kind"] != "simulated" and estimated > 0)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            existing = conn.execute(
                """SELECT * FROM football_brief.renderer_preflight_records
                   WHERE portfolio_content_id=%s AND content_version=%s AND request_fingerprint=%s""",
                (request.portfolio_content_id, request.content_version, fingerprint),
            ).fetchone()
            if existing:
                return {"ok": True, "preflight": dict(existing), "reused": True}
            row = conn.execute(
                """INSERT INTO football_brief.renderer_preflight_records
                   (portfolio_content_id,content_version,renderer_catalogue_entry_id,operation,
                    request_fingerprint,request_payload,accepted,rejection_reasons,estimated_cost,
                    pricing_currency,expected_seconds,external_fee_possible,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (
                    request.portfolio_content_id,
                    request.content_version,
                    entry["id"] if entry else None,
                    request.operation.value,
                    fingerprint,
                    _json(request_payload),
                    accepted,
                    _json(reasons),
                    estimated,
                    entry["pricing_currency"] if entry else "USD",
                    expected,
                    external_fee_possible,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "preflight": dict(row), "reused": False}

    def enqueue_simulated(
        self,
        *,
        request: SimulatedJobRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_active_operator(conn, actor)
            row = conn.execute(
                """SELECT rp.*,rce.provider_key,rce.model_key,rce.adapter_kind,rce.status AS entry_status,
                          rce.health_status,pc.version AS current_content_version
                   FROM football_brief.renderer_preflight_records rp
                   JOIN football_brief.renderer_catalogue_entries rce
                     ON rce.id=rp.renderer_catalogue_entry_id
                   JOIN football_brief.portfolio_content pc ON pc.id=rp.portfolio_content_id
                   WHERE rp.id=%s""",
                (request.renderer_preflight_id,),
            ).fetchone()
        if not row:
            raise RendererCatalogueError("renderer_preflight_not_found")
        if not row["accepted"]:
            raise RendererCatalogueError("renderer_preflight_rejected")
        if row["adapter_kind"] != "simulated" or row["provider_key"] != "simulated":
            raise RendererCatalogueError("paid_renderer_execution_disabled")
        if row["entry_status"] != "active" or row["health_status"] not in {"healthy", "degraded"}:
            raise RendererCatalogueError("renderer_not_available")
        if int(row["current_content_version"]) != int(row["content_version"]):
            raise RendererCatalogueError("content_version_conflict")

        input_payload = {
            "renderer_preflight_id": str(row["id"]),
            "renderer_catalogue_entry_id": str(row["renderer_catalogue_entry_id"]),
            "request_fingerprint": row["request_fingerprint"],
            "request": dict(row["request_payload"]),
            "external_fee_incurred": False,
        }
        job = self.jobs.enqueue(
            GenerationJobEnqueue(
                portfolio_content_id=row["portfolio_content_id"],
                content_version=int(row["content_version"]),
                production_workflow_id=request.production_workflow_id,
                production_workflow_version_id=request.production_workflow_version_id,
                job_type=GenerationJobType.PREMIUM_CLIP,
                provider=row["provider_key"],
                model_id=row["model_key"],
                preferred_worker_id=request.preferred_worker_id,
                priority=request.priority,
                idempotency_key=f"renderer:{row['id']}",
                input_payload=input_payload,
                timeout_seconds=request.timeout_seconds,
                max_attempts=request.max_attempts,
                estimated_cost_usd=Decimal("0"),
                reserved_cost_usd=Decimal("0"),
            ),
            actor=actor,
        )
        with self.database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.renderer_job_bindings
                   (generation_job_id,renderer_preflight_id,renderer_catalogue_entry_id,
                    request_fingerprint,created_by)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (generation_job_id) DO NOTHING""",
                (
                    job["id"],
                    row["id"],
                    row["renderer_catalogue_entry_id"],
                    row["request_fingerprint"],
                    actor,
                ),
            )
        return {"ok": True, "job": job, "preflight": dict(row)}

    @staticmethod
    def _rejection_reasons(entry: dict[str, Any], request: RendererCapabilityRequest) -> list[str]:
        reasons: list[str] = []
        if entry["health_status"] == "unavailable":
            reasons.append("renderer_unavailable")
        if not entry["commercial_use_allowed"]:
            reasons.append("commercial_use_not_allowed")
        if request.format not in set(entry["supported_formats"] or []):
            reasons.append("unsupported_format")
        duration = _decimal(request.duration_seconds)
        minimum = _decimal(entry["min_duration_seconds"])
        maximum = _decimal(entry["max_duration_seconds"])
        if duration < minimum or duration > maximum:
            reasons.append("unsupported_duration")
        step = entry["duration_step_seconds"]
        if step is not None and duration >= minimum:
            remainder = (duration - minimum) % _decimal(step)
            if remainder != 0:
                reasons.append("unsupported_duration_step")
        resolutions = {
            (int(item.get("width", 0)), int(item.get("height", 0)))
            for item in entry["supported_resolutions"] or []
        }
        if (request.width, request.height) not in resolutions:
            reasons.append("unsupported_resolution")
        available = dict(entry["capabilities"] or {})
        for capability in request.required_capabilities:
            if not bool(available.get(capability)):
                reasons.append(f"missing_capability:{capability}")
        return reasons

    @staticmethod
    def _estimate_cost(entry: dict[str, Any], request: RendererCapabilityRequest) -> Decimal:
        pricing = dict(entry["pricing"] or {})
        duration = _decimal(request.duration_seconds)
        megapixels = Decimal(request.width * request.height) / Decimal("1000000")
        return (
            _decimal(pricing.get("base_usd"))
            + _decimal(pricing.get("per_second_usd")) * duration
            + _decimal(pricing.get("per_megapixel_second_usd")) * megapixels * duration
        ).quantize(Decimal("0.000001"))

    @staticmethod
    def _expected_seconds(entry: dict[str, Any], request: RendererCapabilityRequest) -> int | None:
        latency = dict(entry["expected_latency_seconds"] or {})
        base = latency.get("p50") or latency.get("minimum")
        if base is None:
            return None
        multiplier = Decimal(str(latency.get("per_output_second", 0)))
        return max(0, int(Decimal(str(base)) + multiplier * request.duration_seconds))

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not row:
            raise RendererCatalogueError("operator_inactive_or_missing")
