from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from uuid import UUID

from src.application.renderers.adapters import (
    ProductionRendererAdapter,
    RendererAdapterError,
    default_adapter_registry,
)
from src.application.renderers.models import (
    RendererCatalogueCreate,
    RendererHealthUpdate,
    RendererRepriceRequest,
    RendererResolveRequest,
    RendererSubmissionRequest,
    RendererSupportRequest,
    quantize_money,
    quantize_seconds,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class RendererCatalogueError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def canonical_fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _entry_snapshot(entry: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "renderer_key",
        "version",
        "display_name",
        "adapter_key",
        "operation",
        "output_formats",
        "min_duration_seconds",
        "max_duration_seconds",
        "max_width",
        "max_height",
        "capabilities",
        "expected_seconds_base",
        "expected_seconds_per_second",
        "base_cost_usd",
        "cost_per_second_usd",
        "usage_evidence",
        "health",
        "quality_rating",
        "status",
        "simulated",
        "execution_enabled",
        "configuration",
    )
    return {key: entry.get(key) for key in keys}


def evaluate_renderer_support(
    entry: Mapping[str, Any],
    request: RendererSupportRequest,
    *,
    for_submission: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if str(entry.get("status")) != "active":
        reasons.append("renderer_not_active")
    if str(entry.get("health")) == "unavailable":
        reasons.append("renderer_unavailable")
    if str(entry.get("operation")) != request.operation.value:
        reasons.append("operation_not_supported")
    formats = {str(value).strip().lower().lstrip(".") for value in entry.get("output_formats") or []}
    if request.output_format not in formats:
        reasons.append("format_not_supported")
    duration = Decimal(str(request.duration_seconds))
    minimum = Decimal(str(entry.get("min_duration_seconds", 0)))
    maximum = Decimal(str(entry.get("max_duration_seconds", 0)))
    if duration < minimum or duration > maximum:
        reasons.append("duration_not_supported")
    if request.width > int(entry.get("max_width", 0)) or request.height > int(entry.get("max_height", 0)):
        reasons.append("resolution_not_supported")
    available_capabilities = {
        str(value).strip().lower() for value in entry.get("capabilities") or [] if str(value).strip()
    }
    missing = sorted(set(request.required_capabilities) - available_capabilities)
    if missing:
        reasons.append("capability_not_supported")
    if for_submission:
        if not bool(entry.get("execution_enabled")):
            reasons.append("renderer_execution_disabled")
        if not bool(entry.get("simulated")):
            reasons.append("live_renderer_submission_not_enabled")
        if str(entry.get("health")) == "unknown":
            reasons.append("renderer_health_unverified")

    expected_seconds = quantize_seconds(
        Decimal(str(entry.get("expected_seconds_base", 0)))
        + Decimal(str(entry.get("expected_seconds_per_second", 0))) * duration
    )
    estimated_cost_usd = quantize_money(
        Decimal(str(entry.get("base_cost_usd", 0)))
        + Decimal(str(entry.get("cost_per_second_usd", 0))) * duration
    )
    return {
        "supported": not reasons,
        "reasons": reasons,
        "missing_capabilities": missing,
        "expected_seconds": expected_seconds,
        "estimated_cost_usd": estimated_cost_usd,
    }


class RendererCatalogueService:
    def __init__(
        self,
        database: "Database",
        *,
        adapters: Mapping[str, ProductionRendererAdapter] | None = None,
    ) -> None:
        self.database = database
        self.adapters = dict(adapters or default_adapter_registry())

    def list_entries(
        self,
        *,
        statuses: Iterable[str] = (),
        operations: Iterable[str] = (),
        renderer_key: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["true"]
        values: list[Any] = []
        normalized_statuses = sorted({str(value).strip().lower() for value in statuses if str(value).strip()})
        normalized_operations = sorted(
            {str(value).strip().lower() for value in operations if str(value).strip()}
        )
        if normalized_statuses:
            conditions.append("status = ANY(%s::text[])")
            values.append(normalized_statuses)
        if normalized_operations:
            conditions.append("operation = ANY(%s::text[])")
            values.append(normalized_operations)
        if renderer_key:
            conditions.append("renderer_key=%s")
            values.append(renderer_key.strip().lower())
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT * FROM football_brief.production_renderer_catalogue
                    WHERE {' AND '.join(conditions)}
                    ORDER BY renderer_key, version DESC""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_draft(
        self,
        request: RendererCatalogueCreate,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (request.renderer_key,))
            version_row = conn.execute(
                """SELECT COALESCE(MAX(version),0)+1 AS version
                   FROM football_brief.production_renderer_catalogue
                   WHERE renderer_key=%s""",
                (request.renderer_key,),
            ).fetchone()
            version = int(version_row["version"])
            row = conn.execute(
                """INSERT INTO football_brief.production_renderer_catalogue
                   (renderer_key,version,display_name,adapter_key,operation,output_formats,
                    min_duration_seconds,max_duration_seconds,max_width,max_height,capabilities,
                    expected_seconds_base,expected_seconds_per_second,base_cost_usd,
                    cost_per_second_usd,usage_evidence,health,quality_rating,simulated,
                    execution_enabled,configuration,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,
                           %s,%s,%s,%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.renderer_key,
                    version,
                    request.display_name,
                    request.adapter_key,
                    request.operation.value,
                    list(request.output_formats),
                    request.min_duration_seconds,
                    request.max_duration_seconds,
                    request.max_width,
                    request.max_height,
                    list(request.capabilities),
                    request.expected_seconds_base,
                    request.expected_seconds_per_second,
                    request.base_cost_usd,
                    request.cost_per_second_usd,
                    _json(request.usage_evidence),
                    request.health.value,
                    request.quality_rating,
                    request.simulated,
                    request.execution_enabled,
                    _json(request.configuration),
                    actor,
                ),
            ).fetchone()
            self._event(conn, renderer_id=row["id"], event="created", actor=actor, details={})
        return {"ok": True, "renderer": dict(row)}

    def activate(self, *, renderer_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._entry_for_update(conn, renderer_id)
            if row["status"] == "active":
                return {"ok": True, "renderer": dict(row), "already_active": True}
            if row["status"] != "draft":
                raise RendererCatalogueError("only_draft_renderers_can_be_activated")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (row["renderer_key"],))
            previous = conn.execute(
                """SELECT id FROM football_brief.production_renderer_catalogue
                   WHERE renderer_key=%s AND status='active' AND id<>%s FOR UPDATE""",
                (row["renderer_key"], renderer_id),
            ).fetchall()
            for item in previous:
                retired = conn.execute(
                    """UPDATE football_brief.production_renderer_catalogue
                       SET status='retired',retired_by=%s,retired_at=now(),execution_enabled=false
                       WHERE id=%s RETURNING *""",
                    (actor, item["id"]),
                ).fetchone()
                self._event(
                    conn,
                    renderer_id=retired["id"],
                    event="retired",
                    actor=actor,
                    details={"replacement_renderer_id": str(renderer_id)},
                )
            activated = conn.execute(
                """UPDATE football_brief.production_renderer_catalogue
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, renderer_id),
            ).fetchone()
            self._event(conn, renderer_id=renderer_id, event="activated", actor=actor, details={})
        return {"ok": True, "renderer": dict(activated)}

    def retire(self, *, renderer_id: UUID, actor: str, reason: str) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 3:
            raise RendererCatalogueError("retirement_reason_required")
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._entry_for_update(conn, renderer_id)
            if row["status"] == "retired":
                return {"ok": True, "renderer": dict(row), "already_retired": True}
            retired = conn.execute(
                """UPDATE football_brief.production_renderer_catalogue
                   SET status='retired',retired_by=%s,retired_at=now(),execution_enabled=false
                   WHERE id=%s RETURNING *""",
                (actor, renderer_id),
            ).fetchone()
            self._event(
                conn,
                renderer_id=renderer_id,
                event="retired",
                actor=actor,
                details={"reason": normalized_reason},
            )
        return {"ok": True, "renderer": dict(retired)}

    def reprice(
        self,
        *,
        renderer_id: UUID,
        request: RendererRepriceRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            source = self._entry_for_update(conn, renderer_id)
            if source["status"] != "active":
                raise RendererCatalogueError("only_active_renderers_can_be_repriced")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (source["renderer_key"],))
            next_version = int(
                conn.execute(
                    """SELECT COALESCE(MAX(version),0)+1 AS version
                       FROM football_brief.production_renderer_catalogue
                       WHERE renderer_key=%s""",
                    (source["renderer_key"],),
                ).fetchone()["version"]
            )
            retired = conn.execute(
                """UPDATE football_brief.production_renderer_catalogue
                   SET status='retired',retired_by=%s,retired_at=now(),execution_enabled=false
                   WHERE id=%s RETURNING *""",
                (actor, renderer_id),
            ).fetchone()
            replacement = conn.execute(
                """INSERT INTO football_brief.production_renderer_catalogue
                   (renderer_key,version,parent_renderer_id,display_name,adapter_key,operation,
                    output_formats,min_duration_seconds,max_duration_seconds,max_width,max_height,
                    capabilities,expected_seconds_base,expected_seconds_per_second,base_cost_usd,
                    cost_per_second_usd,usage_evidence,health,quality_rating,status,simulated,
                    execution_enabled,configuration,created_by,activated_by,activated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                           'active',%s,%s,%s::jsonb,%s,%s,now()) RETURNING *""",
                (
                    source["renderer_key"],
                    next_version,
                    source["id"],
                    source["display_name"],
                    source["adapter_key"],
                    source["operation"],
                    source["output_formats"],
                    source["min_duration_seconds"],
                    source["max_duration_seconds"],
                    source["max_width"],
                    source["max_height"],
                    source["capabilities"],
                    source["expected_seconds_base"],
                    source["expected_seconds_per_second"],
                    request.base_cost_usd,
                    request.cost_per_second_usd,
                    _json(source["usage_evidence"] or {}),
                    source["health"],
                    source["quality_rating"],
                    source["simulated"],
                    bool(source["simulated"] and source["execution_enabled"]),
                    _json(source["configuration"] or {}),
                    actor,
                    actor,
                ),
            ).fetchone()
            self._event(
                conn,
                renderer_id=retired["id"],
                event="retired",
                actor=actor,
                details={"reason": "repriced", "replacement_renderer_id": str(replacement["id"])},
            )
            self._event(
                conn,
                renderer_id=replacement["id"],
                event="repriced",
                actor=actor,
                details={
                    "reason": request.reason,
                    "source_renderer_id": str(source["id"]),
                    "previous_base_cost_usd": str(source["base_cost_usd"]),
                    "previous_cost_per_second_usd": str(source["cost_per_second_usd"]),
                },
            )
        return {"ok": True, "renderer": dict(replacement), "retired_renderer": dict(retired)}

    def update_health(
        self,
        *,
        renderer_id: UUID,
        request: RendererHealthUpdate,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._entry_for_update(conn, renderer_id)
            if row["status"] == "retired":
                raise RendererCatalogueError("retired_renderer_health_is_immutable")
            updated = conn.execute(
                """UPDATE football_brief.production_renderer_catalogue
                   SET health=%s,quality_rating=%s,usage_evidence=%s::jsonb
                   WHERE id=%s RETURNING *""",
                (request.health.value, request.quality_rating, _json(request.usage_evidence), renderer_id),
            ).fetchone()
            self._event(
                conn,
                renderer_id=renderer_id,
                event="health_updated",
                actor=actor,
                details={
                    "reason": request.reason,
                    "previous_health": row["health"],
                    "previous_quality_rating": str(row["quality_rating"]),
                },
            )
        return {"ok": True, "renderer": dict(updated)}

    def resolve(self, request: RendererResolveRequest) -> dict[str, Any]:
        entries = self.list_entries(statuses=("active",), renderer_key=request.renderer_key)
        considered: list[dict[str, Any]] = []
        supported: list[tuple[Decimal, Decimal, Decimal, str, int, dict[str, Any], dict[str, Any]]] = []
        support_request = RendererSupportRequest(**request.model_dump(exclude={"renderer_key"}))
        for entry in entries:
            evaluation = evaluate_renderer_support(entry, support_request, for_submission=False)
            considered.append(
                {
                    "renderer_id": entry["id"],
                    "renderer_key": entry["renderer_key"],
                    "version": entry["version"],
                    **evaluation,
                }
            )
            if evaluation["supported"]:
                supported.append(
                    (
                        Decimal(str(evaluation["estimated_cost_usd"])),
                        Decimal(str(evaluation["expected_seconds"])),
                        -Decimal(str(entry["quality_rating"])),
                        str(entry["renderer_key"]),
                        int(entry["version"]),
                        entry,
                        evaluation,
                    )
                )
        if not supported:
            raise RendererCatalogueError(
                "no_supported_renderer",
                details={"considered": considered, "request": support_request.model_dump(mode="json")},
            )
        supported.sort(key=lambda item: item[:5])
        _, _, _, _, _, selected, evaluation = supported[0]
        return {
            "ok": True,
            "renderer": selected,
            "estimate": {
                "expected_seconds": evaluation["expected_seconds"],
                "estimated_cost_usd": evaluation["estimated_cost_usd"],
            },
            "considered": considered,
        }

    def submit_simulated(
        self,
        request: RendererSubmissionRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        request_payload = request.request.model_dump(mode="json")
        fingerprint = canonical_fingerprint(
            {"renderer_id": str(request.renderer_id), "request": request_payload, "input": request.input_payload}
        )
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            entry = self._entry_for_update(conn, request.renderer_id)
            evaluation = evaluate_renderer_support(entry, request.request, for_submission=True)
            if not evaluation["supported"]:
                raise RendererCatalogueError(
                    "renderer_submission_not_supported",
                    details={"reasons": evaluation["reasons"], "renderer_id": str(request.renderer_id)},
                )
            adapter = self.adapters.get(str(entry["adapter_key"]))
            if adapter is None:
                raise RendererCatalogueError("renderer_adapter_not_configured")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (request.idempotency_key,))
            existing = conn.execute(
                """SELECT * FROM football_brief.production_renderer_attempts
                   WHERE idempotency_key=%s FOR UPDATE""",
                (request.idempotency_key,),
            ).fetchone()
            if existing:
                if existing["input_fingerprint"] != fingerprint:
                    raise RendererCatalogueError("renderer_idempotency_conflict")
                return {"ok": existing["status"] == "succeeded", "attempt": dict(existing), "reused": True}
            attempt = conn.execute(
                """INSERT INTO football_brief.production_renderer_attempts
                   (renderer_id,idempotency_key,input_fingerprint,request_spec,input_payload,
                    catalogue_snapshot,status,estimated_cost_usd,expected_seconds,submitted_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,'running',%s,%s,%s)
                   RETURNING *""",
                (
                    request.renderer_id,
                    request.idempotency_key,
                    fingerprint,
                    _json(request_payload),
                    _json(request.input_payload),
                    _json(_entry_snapshot(entry)),
                    evaluation["estimated_cost_usd"],
                    evaluation["expected_seconds"],
                    actor,
                ),
            ).fetchone()
        try:
            result = adapter.submit(request, catalogue_entry=dict(entry))
        except RendererAdapterError as exc:
            with self.database.transaction() as conn:
                failed = conn.execute(
                    """UPDATE football_brief.production_renderer_attempts
                       SET status='failed',error_code=%s,error_message=%s,finished_at=now()
                       WHERE id=%s AND status='running' RETURNING *""",
                    (exc.code, exc.message, attempt["id"]),
                ).fetchone()
            raise RendererCatalogueError(
                "renderer_submission_failed",
                details={"attempt_id": str(failed["id"]), "error_code": exc.code},
            ) from exc
        with self.database.transaction() as conn:
            succeeded = conn.execute(
                """UPDATE football_brief.production_renderer_attempts
                   SET status='succeeded',provider_request_id=%s,output_payload=%s::jsonb,
                       actual_cost_usd=%s,finished_at=now()
                   WHERE id=%s AND status='running' RETURNING *""",
                (
                    result.provider_request_id,
                    _json(result.output_payload),
                    result.actual_cost_usd,
                    attempt["id"],
                ),
            ).fetchone()
        return {"ok": True, "attempt": dict(succeeded), "reused": False}

    def attempt(self, *, attempt_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT a.*,r.renderer_key,r.version AS renderer_version,r.display_name
                   FROM football_brief.production_renderer_attempts a
                   JOIN football_brief.production_renderer_catalogue r ON r.id=a.renderer_id
                   WHERE a.id=%s""",
                (attempt_id,),
            ).fetchone()
        if not row:
            raise RendererCatalogueError("renderer_attempt_not_found")
        return {"ok": True, "attempt": dict(row)}

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]):
            raise RendererCatalogueError("operator_inactive_or_missing")

    @staticmethod
    def _entry_for_update(conn: Any, renderer_id: UUID) -> Mapping[str, Any]:
        row = conn.execute(
            "SELECT * FROM football_brief.production_renderer_catalogue WHERE id=%s FOR UPDATE",
            (renderer_id,),
        ).fetchone()
        if not row:
            raise RendererCatalogueError("renderer_not_found")
        return row

    @staticmethod
    def _event(
        conn: Any,
        *,
        renderer_id: UUID,
        event: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.production_renderer_events
               (renderer_id,event,actor_operator_id,details)
               VALUES (%s,%s,%s,%s::jsonb)""",
            (renderer_id, event, actor, _json(details)),
        )
