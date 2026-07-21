from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from uuid import UUID, uuid4

from src.application.delivery.adapters import (
    DeliveryAdapterError,
    PlatformDeliveryAdapter,
    default_delivery_adapters,
)
from src.application.delivery.models import (
    DeliveryAdapterRequest,
    DeliveryCancelRequest,
    DeliveryClaimRequest,
    DeliveryCreateRequest,
    DeliveryExecuteRequest,
    DeliveryTargetRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class PlatformDeliveryError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class PlatformDeliveryService:
    def __init__(
        self,
        database: "Database",
        *,
        adapters: Mapping[str, PlatformDeliveryAdapter] | None = None,
    ) -> None:
        self.database = database
        self.adapters = dict(adapters or default_delivery_adapters())

    def create_target(
        self,
        request: DeliveryTargetRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"delivery-target:{request.target_key}",),
            )
            existing = conn.execute(
                "SELECT id FROM football_brief.platform_delivery_targets WHERE target_key=%s LIMIT 1",
                (request.target_key,),
            ).fetchone()
            if existing:
                raise PlatformDeliveryError("delivery_target_key_exists")
            row = self._insert_target(
                conn,
                request=request,
                version=1,
                parent_id=None,
                status="draft",
                actor=actor,
            )
            self._event(
                conn,
                target_id=row["id"],
                event="target_created",
                actor=actor,
                details={"target_key": row["target_key"], "version": 1},
            )
        return {"ok": True, "target": dict(row)}

    def activate_target(self, *, target_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            target = self._target_for_update(conn, target_id)
            if target["status"] == "active":
                return {"ok": True, "target": dict(target), "already_active": True}
            if target["status"] not in {"draft", "unavailable"}:
                raise PlatformDeliveryError(
                    "delivery_target_not_activatable",
                    details={"status": target["status"]},
                )
            self._require_target_adapters(target)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"delivery-target:{target['target_key']}",),
            )
            active = conn.execute(
                """SELECT id FROM football_brief.platform_delivery_targets
                   WHERE target_key=%s AND status='active' AND id<>%s FOR UPDATE""",
                (target["target_key"], target_id),
            ).fetchone()
            if active:
                raise PlatformDeliveryError(
                    "delivery_target_active_version_exists",
                    details={"active_target_id": str(active["id"])},
                )
            row = conn.execute(
                """UPDATE football_brief.platform_delivery_targets
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, target_id),
            ).fetchone()
            self._event(
                conn,
                target_id=target_id,
                event="target_activated",
                actor=actor,
                details={"version": int(row["version"])},
            )
        return {"ok": True, "target": dict(row), "already_active": False}

    def revise_target(
        self,
        *,
        target_id: UUID,
        request: DeliveryTargetRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = self._target_for_update(conn, target_id)
            if current["status"] != "active" or current["target_key"] != request.target_key:
                raise PlatformDeliveryError("delivery_target_revision_requires_active_matching_key")
            pending = conn.execute(
                """SELECT count(*) AS count FROM football_brief.platform_delivery_requests
                   WHERE target_id=%s AND status IN ('queued','processing','retry_wait')""",
                (target_id,),
            ).fetchone()["count"]
            if pending:
                raise PlatformDeliveryError(
                    "delivery_target_has_pending_requests",
                    details={"pending_count": int(pending)},
                )
            self._require_request_adapters(request)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"delivery-target:{current['target_key']}",),
            )
            retired = conn.execute(
                """UPDATE football_brief.platform_delivery_targets
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, target_id),
            ).fetchone()
            replacement = self._insert_target(
                conn,
                request=request,
                version=int(current["version"]) + 1,
                parent_id=target_id,
                status="active",
                actor=actor,
            )
            self._event(
                conn,
                target_id=replacement["id"],
                event="target_revised",
                actor=actor,
                details={
                    "source_target_id": str(target_id),
                    "version": int(replacement["version"]),
                },
            )
        return {
            "ok": True,
            "target": dict(replacement),
            "retired_target": dict(retired),
        }

    def mark_target_unavailable(
        self,
        *,
        target_id: UUID,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized = reason.strip()
        if len(normalized) < 3:
            raise PlatformDeliveryError("delivery_target_unavailable_reason_required")
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            target = self._target_for_update(conn, target_id)
            if target["status"] != "active":
                raise PlatformDeliveryError("delivery_target_not_active")
            row = conn.execute(
                """UPDATE football_brief.platform_delivery_targets
                   SET status='unavailable' WHERE id=%s RETURNING *""",
                (target_id,),
            ).fetchone()
            self._event(
                conn,
                target_id=target_id,
                event="target_unavailable",
                actor=actor,
                details={"reason": normalized},
            )
        return {"ok": True, "target": dict(row)}

    def retire_target(
        self,
        *,
        target_id: UUID,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized = reason.strip()
        if len(normalized) < 3:
            raise PlatformDeliveryError("delivery_target_retirement_reason_required")
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            target = self._target_for_update(conn, target_id)
            if target["status"] == "retired":
                return {"ok": True, "target": dict(target), "already_retired": True}
            pending = conn.execute(
                """SELECT count(*) AS count FROM football_brief.platform_delivery_requests
                   WHERE target_id=%s AND status IN ('queued','processing','retry_wait')""",
                (target_id,),
            ).fetchone()["count"]
            if pending:
                raise PlatformDeliveryError(
                    "delivery_target_has_pending_requests",
                    details={"pending_count": int(pending)},
                )
            row = conn.execute(
                """UPDATE football_brief.platform_delivery_targets
                   SET status='retired',retired_by=%s,retired_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, target_id),
            ).fetchone()
            self._event(
                conn,
                target_id=target_id,
                event="target_retired",
                actor=actor,
                details={"reason": normalized},
            )
        return {"ok": True, "target": dict(row), "already_retired": False}

    def list_targets(self, *, include_retired: bool = False) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_targets
                   WHERE %s OR status<>'retired'
                   ORDER BY target_key,version DESC""",
                (include_retired,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_delivery(
        self,
        request: DeliveryCreateRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        now = _utcnow()
        with self.database.transaction() as conn:
            self._require_publisher(conn, actor)
            release = conn.execute(
                "SELECT * FROM football_brief.final_releases WHERE id=%s FOR SHARE",
                (request.final_release_id,),
            ).fetchone()
            if not release:
                raise PlatformDeliveryError("final_release_not_found")
            target = conn.execute(
                "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s FOR SHARE",
                (request.target_id,),
            ).fetchone()
            if not target:
                raise PlatformDeliveryError("delivery_target_not_found")
            privacy = request.privacy.value if request.privacy else target["default_privacy"]
            fingerprint = _hash(
                {
                    "release_manifest_hash": release["manifest_hash"],
                    "target_key": target["target_key"],
                    "privacy": privacy,
                }
            )
            existing_key = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_requests
                   WHERE target_id=%s AND idempotency_key=%s FOR UPDATE""",
                (request.target_id, request.idempotency_key),
            ).fetchone()
            if existing_key:
                if (
                    existing_key["delivery_fingerprint"] != fingerprint
                    or existing_key["final_release_id"] != request.final_release_id
                ):
                    raise PlatformDeliveryError("delivery_idempotency_conflict")
                return {"ok": True, "delivery": dict(existing_key), "reused": True}
            existing_fingerprint = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_requests
                   WHERE delivery_fingerprint=%s FOR UPDATE""",
                (fingerprint,),
            ).fetchone()
            if existing_fingerprint:
                return {
                    "ok": True,
                    "delivery": dict(existing_fingerprint),
                    "reused": True,
                    "duplicate_prevented": True,
                }
            scheduled_for = request.scheduled_for or now
            row = conn.execute(
                """INSERT INTO football_brief.platform_delivery_requests
                   (final_release_id,target_id,release_manifest_hash,delivery_fingerprint,
                    idempotency_key,privacy,scheduled_for,next_attempt_at,status,max_attempts,
                    metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s::jsonb,%s)
                   RETURNING *""",
                (
                    request.final_release_id,
                    request.target_id,
                    release["manifest_hash"],
                    fingerprint,
                    request.idempotency_key,
                    privacy,
                    scheduled_for,
                    max(scheduled_for, now),
                    request.max_attempts,
                    _json(request.metadata),
                    actor,
                ),
            ).fetchone()
            self._event(
                conn,
                delivery_request_id=row["id"],
                target_id=target["id"],
                event="delivery_created",
                actor=actor,
                details={
                    "scheduled_for": scheduled_for.isoformat(),
                    "privacy": privacy,
                    "release_manifest_hash": release["manifest_hash"],
                },
            )
        return {"ok": True, "delivery": dict(row), "reused": False}

    def claim_due(
        self,
        request: DeliveryClaimRequest,
        *,
        allowed_brand_ids: Iterable[UUID] | None,
    ) -> dict[str, Any] | None:
        now = _utcnow()
        lease_expires_at = now + timedelta(seconds=request.lease_seconds)
        normalized_brands = (
            [UUID(str(value)) for value in allowed_brand_ids]
            if allowed_brand_ids is not None
            else None
        )
        if normalized_brands is not None and not normalized_brands:
            return None
        with self.database.transaction() as conn:
            self._require_publisher(conn, request.worker_id)
            self._recover_expired_locked(conn, now=now, actor=request.worker_id, limit=25)
            conditions = [
                "pdr.status IN ('queued','retry_wait')",
                "pdr.scheduled_for<=%s",
                "pdr.next_attempt_at<=%s",
                "pdr.attempt_count<pdr.max_attempts",
                "fr.status='approved'",
                "fr.manifest_hash=pdr.release_manifest_hash",
                "pdt.status='active'",
                "pdt.execution_enabled=true",
                "pdt.simulated=true",
            ]
            values: list[Any] = [now, now]
            if request.target_ids:
                conditions.append("pdr.target_id=ANY(%s::uuid[])")
                values.append(list(request.target_ids))
            if normalized_brands is not None:
                conditions.append("mp.brand_id=ANY(%s::uuid[])")
                values.append(normalized_brands)
            rows = conn.execute(
                f"""SELECT pdr.*,pdt.target_key,pdt.requests_per_minute,pdt.requests_per_day,
                           mp.brand_id
                    FROM football_brief.platform_delivery_requests pdr
                    JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
                    JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
                    JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY pdr.next_attempt_at,pdr.scheduled_for,pdr.created_at,pdr.id
                    FOR UPDATE OF pdr SKIP LOCKED
                    LIMIT 25""",
                tuple(values),
            ).fetchall()
            selected = None
            for row in rows:
                target = conn.execute(
                    "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s FOR UPDATE",
                    (row["target_id"],),
                ).fetchone()
                if self._rate_limited(conn, target, now=now):
                    delay_until = now + timedelta(minutes=1)
                    conn.execute(
                        """UPDATE football_brief.platform_delivery_requests
                           SET next_attempt_at=%s WHERE id=%s""",
                        (delay_until, row["id"]),
                    )
                    continue
                selected = row
                break
            if selected is None:
                return None
            lease_token = uuid4()
            claimed = conn.execute(
                """UPDATE football_brief.platform_delivery_requests
                   SET status='processing',attempt_count=attempt_count+1,
                       current_worker_id=%s,lease_token=%s,lease_expires_at=%s,
                       started_at=COALESCE(started_at,%s),
                       last_error_code=NULL,last_error_message=NULL,last_error_retryable=NULL
                   WHERE id=%s RETURNING *""",
                (
                    request.worker_id,
                    lease_token,
                    lease_expires_at,
                    now,
                    selected["id"],
                ),
            ).fetchone()
            self._event(
                conn,
                delivery_request_id=claimed["id"],
                target_id=claimed["target_id"],
                event="delivery_claimed",
                actor=request.worker_id,
                details={
                    "attempt_count": int(claimed["attempt_count"]),
                    "lease_expires_at": lease_expires_at.isoformat(),
                },
            )
        return {
            "ok": True,
            "delivery": dict(claimed),
            "lease_token": lease_token,
            "lease_expires_at": lease_expires_at,
        }

    def execute_claim(self, request: DeliveryExecuteRequest) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_publisher(conn, request.worker_id)
            delivery, target, adapter_request = self._claimed_context_for_update(
                conn,
                request=request,
            )
            primary = self.adapters.get(target["primary_adapter_key"])
            if primary is None:
                raise PlatformDeliveryError("delivery_primary_adapter_not_configured")
            primary_attempt = self._start_attempt(
                conn,
                delivery=delivery,
                target=target,
                transport="primary",
                adapter_key=target["primary_adapter_key"],
                request_snapshot=adapter_request.model_dump(mode="json"),
                worker_id=request.worker_id,
            )

        try:
            result = primary.deliver(adapter_request, target=dict(target))
        except DeliveryAdapterError as primary_error:
            self._finish_attempt_failure(primary_attempt["id"], primary_error)
            fallback_key = target["fallback_adapter_key"]
            should_fallback = bool(
                fallback_key
                and primary_error.code in {
                    "simulated_primary_unsupported",
                    "simulated_primary_unavailable",
                }
            )
            if should_fallback:
                fallback = self.adapters.get(fallback_key)
                if fallback is None:
                    return self._finalize_failure(
                        request.delivery_request_id,
                        worker_id=request.worker_id,
                        error_code="delivery_fallback_adapter_not_configured",
                        error_message="The configured fallback adapter is unavailable.",
                        retryable=primary_error.retryable,
                    )
                with self.database.transaction() as conn:
                    current = self._validate_processing_lease(
                        conn,
                        delivery_request_id=request.delivery_request_id,
                        worker_id=request.worker_id,
                        lease_token=request.lease_token,
                    )
                    fallback_attempt = self._start_attempt(
                        conn,
                        delivery=current,
                        target=target,
                        transport="fallback",
                        adapter_key=fallback_key,
                        request_snapshot=adapter_request.model_dump(mode="json"),
                        worker_id=request.worker_id,
                    )
                try:
                    fallback_result = fallback.deliver(adapter_request, target=dict(target))
                except DeliveryAdapterError as fallback_error:
                    self._finish_attempt_failure(fallback_attempt["id"], fallback_error)
                    return self._finalize_failure(
                        request.delivery_request_id,
                        worker_id=request.worker_id,
                        error_code=fallback_error.code,
                        error_message=fallback_error.message,
                        retryable=primary_error.retryable or fallback_error.retryable,
                    )
                self._finish_attempt_success(fallback_attempt["id"], fallback_result)
                return self._finalize_success(
                    request.delivery_request_id,
                    worker_id=request.worker_id,
                    result=fallback_result,
                    transport="fallback",
                )
            return self._finalize_failure(
                request.delivery_request_id,
                worker_id=request.worker_id,
                error_code=primary_error.code,
                error_message=primary_error.message,
                retryable=primary_error.retryable,
            )

        self._finish_attempt_success(primary_attempt["id"], result)
        return self._finalize_success(
            request.delivery_request_id,
            worker_id=request.worker_id,
            result=result,
            transport="primary",
        )

    def cancel_delivery(
        self,
        *,
        delivery_request_id: UUID,
        request: DeliveryCancelRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_publisher(conn, actor)
            row = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_requests
                   WHERE id=%s FOR UPDATE""",
                (delivery_request_id,),
            ).fetchone()
            if not row:
                raise PlatformDeliveryError("delivery_request_not_found")
            if row["status"] == "cancelled":
                return {"ok": True, "delivery": dict(row), "already_cancelled": True}
            if row["status"] not in {"queued", "retry_wait"}:
                raise PlatformDeliveryError(
                    "delivery_request_not_cancellable",
                    details={"status": row["status"]},
                )
            cancelled = conn.execute(
                """UPDATE football_brief.platform_delivery_requests
                   SET status='cancelled',cancelled_at=now(),cancelled_by=%s
                   WHERE id=%s RETURNING *""",
                (actor, delivery_request_id),
            ).fetchone()
            self._event(
                conn,
                delivery_request_id=delivery_request_id,
                target_id=cancelled["target_id"],
                event="delivery_cancelled",
                actor=actor,
                details={"rationale": request.rationale},
            )
        return {"ok": True, "delivery": dict(cancelled), "already_cancelled": False}

    def detail(self, *, delivery_request_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            delivery = conn.execute(
                """SELECT pdr.*,pdt.target_key,pdt.platform,pdt.display_name AS target_name,
                          fr.version AS release_version,fr.portfolio_content_id,fr.content_version,
                          mp.brand_id,b.slug AS brand_slug
                   FROM football_brief.platform_delivery_requests pdr
                   JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
                   JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE pdr.id=%s""",
                (delivery_request_id,),
            ).fetchone()
            if not delivery:
                raise PlatformDeliveryError("delivery_request_not_found")
            attempts = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_attempts
                   WHERE delivery_request_id=%s ORDER BY sequence_number""",
                (delivery_request_id,),
            ).fetchall()
            events = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_events
                   WHERE delivery_request_id=%s ORDER BY created_at,id""",
                (delivery_request_id,),
            ).fetchall()
        return {
            "ok": True,
            "delivery": dict(delivery),
            "attempts": [dict(row) for row in attempts],
            "events": [dict(row) for row in events],
        }

    def list_deliveries(
        self,
        *,
        brand_ids: Iterable[UUID] | None = None,
        statuses: Iterable[str] = (),
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise PlatformDeliveryError("invalid_delivery_list_limit")
        conditions = ["true"]
        values: list[Any] = []
        normalized_brands = (
            [UUID(str(value)) for value in brand_ids]
            if brand_ids is not None
            else None
        )
        if normalized_brands is not None:
            if not normalized_brands:
                return []
            conditions.append("mp.brand_id=ANY(%s::uuid[])")
            values.append(normalized_brands)
        normalized_statuses = sorted({str(value).strip().lower() for value in statuses if str(value).strip()})
        if normalized_statuses:
            conditions.append("pdr.status=ANY(%s::text[])")
            values.append(normalized_statuses)
        values.append(limit)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT pdr.*,pdt.target_key,pdt.platform,fr.portfolio_content_id,
                           fr.content_version,fr.version AS release_version,mp.brand_id,b.slug AS brand_slug
                    FROM football_brief.platform_delivery_requests pdr
                    JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
                    JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
                    JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                    JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                    JOIN football_brief.brands b ON b.id=mp.brand_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY pdr.created_at DESC,pdr.id DESC
                    LIMIT %s""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def _claimed_context_for_update(
        self,
        conn: Any,
        *,
        request: DeliveryExecuteRequest,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], DeliveryAdapterRequest]:
        delivery = self._validate_processing_lease(
            conn,
            delivery_request_id=request.delivery_request_id,
            worker_id=request.worker_id,
            lease_token=request.lease_token,
        )
        target = conn.execute(
            "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s FOR SHARE",
            (delivery["target_id"],),
        ).fetchone()
        release = conn.execute(
            "SELECT * FROM football_brief.final_releases WHERE id=%s FOR SHARE",
            (delivery["final_release_id"],),
        ).fetchone()
        output = conn.execute(
            """SELECT sav.id,a.sha256
               FROM football_brief.shared_artifact_versions sav
               JOIN football_brief.assets a ON a.id=sav.original_asset_id
               WHERE sav.id=%s""",
            (release["output_artifact_version_id"],),
        ).fetchone()
        if release["status"] != "approved" or release["manifest_hash"] != delivery["release_manifest_hash"]:
            raise PlatformDeliveryError("delivery_release_no_longer_approved")
        if target["status"] != "active" or not target["execution_enabled"] or not target["simulated"]:
            raise PlatformDeliveryError("delivery_target_no_longer_executable")
        adapter_request = DeliveryAdapterRequest(
            delivery_request_id=delivery["id"],
            delivery_fingerprint=delivery["delivery_fingerprint"],
            platform=target["platform"],
            target_key=target["target_key"],
            privacy=delivery["privacy"],
            release_manifest_hash=release["manifest_hash"],
            release_manifest=release["release_manifest"],
            output_artifact_version_id=output["id"],
            output_asset_sha256=output["sha256"],
            metadata=delivery["metadata"],
        )
        return delivery, target, adapter_request

    def _validate_processing_lease(
        self,
        conn: Any,
        *,
        delivery_request_id: UUID,
        worker_id: str,
        lease_token: UUID,
    ) -> Mapping[str, Any]:
        row = conn.execute(
            """SELECT * FROM football_brief.platform_delivery_requests
               WHERE id=%s FOR UPDATE""",
            (delivery_request_id,),
        ).fetchone()
        if not row:
            raise PlatformDeliveryError("delivery_request_not_found")
        if row["status"] == "succeeded":
            return row
        if row["status"] != "processing":
            raise PlatformDeliveryError(
                "delivery_request_not_processing",
                details={"status": row["status"]},
            )
        if row["current_worker_id"] != worker_id or row["lease_token"] != lease_token:
            raise PlatformDeliveryError("delivery_lease_mismatch")
        if row["lease_expires_at"] <= _utcnow():
            raise PlatformDeliveryError("delivery_lease_expired")
        return row

    def _start_attempt(
        self,
        conn: Any,
        *,
        delivery: Mapping[str, Any],
        target: Mapping[str, Any],
        transport: str,
        adapter_key: str,
        request_snapshot: dict[str, Any],
        worker_id: str,
    ) -> Mapping[str, Any]:
        sequence = int(
            conn.execute(
                """SELECT COALESCE(max(sequence_number),0)+1 AS sequence
                   FROM football_brief.platform_delivery_attempts
                   WHERE delivery_request_id=%s""",
                (delivery["id"],),
            ).fetchone()["sequence"]
        )
        attempt = conn.execute(
            """INSERT INTO football_brief.platform_delivery_attempts
               (delivery_request_id,sequence_number,cycle_number,transport,adapter_key,
                status,request_snapshot,worker_id)
               VALUES (%s,%s,%s,%s,%s,'running',%s::jsonb,%s) RETURNING *""",
            (
                delivery["id"],
                sequence,
                delivery["attempt_count"],
                transport,
                adapter_key,
                _json(request_snapshot),
                worker_id,
            ),
        ).fetchone()
        self._event(
            conn,
            delivery_request_id=delivery["id"],
            target_id=target["id"],
            event="primary_attempted" if transport == "primary" else "fallback_attempted",
            actor=worker_id,
            details={
                "attempt_id": str(attempt["id"]),
                "sequence_number": sequence,
                "cycle_number": int(delivery["attempt_count"]),
                "adapter_key": adapter_key,
            },
        )
        return attempt

    def _finish_attempt_success(self, attempt_id: UUID, result: Any) -> None:
        with self.database.transaction() as conn:
            updated = conn.execute(
                """UPDATE football_brief.platform_delivery_attempts
                   SET status='succeeded',response_payload=%s::jsonb,provider_request_id=%s,
                       platform_reference=%s,finished_at=now()
                   WHERE id=%s AND status='running' RETURNING id""",
                (
                    _json(result.response_payload),
                    result.provider_request_id,
                    result.platform_reference,
                    attempt_id,
                ),
            ).fetchone()
            if not updated:
                raise PlatformDeliveryError("delivery_attempt_completion_conflict")

    def _finish_attempt_failure(self, attempt_id: UUID, error: DeliveryAdapterError) -> None:
        with self.database.transaction() as conn:
            updated = conn.execute(
                """UPDATE football_brief.platform_delivery_attempts
                   SET status='failed',error_code=%s,error_message=%s,retryable=%s,finished_at=now()
                   WHERE id=%s AND status='running' RETURNING id""",
                (error.code, error.message, error.retryable, attempt_id),
            ).fetchone()
            if not updated:
                raise PlatformDeliveryError("delivery_attempt_completion_conflict")

    def _finalize_success(
        self,
        delivery_request_id: UUID,
        *,
        worker_id: str,
        result: Any,
        transport: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_requests
                   WHERE id=%s FOR UPDATE""",
                (delivery_request_id,),
            ).fetchone()
            if row["status"] == "succeeded":
                return {"ok": True, "delivery": dict(row), "reused": True}
            if row["status"] != "processing" or row["current_worker_id"] != worker_id:
                raise PlatformDeliveryError("delivery_finalization_conflict")
            updated = conn.execute(
                """UPDATE football_brief.platform_delivery_requests
                   SET status='succeeded',platform_reference=%s,completed_at=now(),
                       current_worker_id=NULL,lease_token=NULL,lease_expires_at=NULL,
                       last_error_code=NULL,last_error_message=NULL,last_error_retryable=NULL
                   WHERE id=%s RETURNING *""",
                (result.platform_reference, delivery_request_id),
            ).fetchone()
            self._event(
                conn,
                delivery_request_id=delivery_request_id,
                target_id=updated["target_id"],
                event="delivery_succeeded",
                actor=worker_id,
                details={
                    "platform_reference": result.platform_reference,
                    "provider_request_id": result.provider_request_id,
                    "transport": transport,
                },
            )
        return {"ok": True, "delivery": dict(updated), "reused": False}

    def _finalize_failure(
        self,
        delivery_request_id: UUID,
        *,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> dict[str, Any]:
        now = _utcnow()
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_requests
                   WHERE id=%s FOR UPDATE""",
                (delivery_request_id,),
            ).fetchone()
            if row["status"] != "processing" or row["current_worker_id"] != worker_id:
                raise PlatformDeliveryError("delivery_finalization_conflict")
            can_retry = retryable and int(row["attempt_count"]) < int(row["max_attempts"])
            if can_retry:
                delay_seconds = min(3600, 60 * (2 ** max(0, int(row["attempt_count"]) - 1)))
                next_attempt_at = now + timedelta(seconds=delay_seconds)
                updated = conn.execute(
                    """UPDATE football_brief.platform_delivery_requests
                       SET status='retry_wait',next_attempt_at=%s,
                           last_error_code=%s,last_error_message=%s,last_error_retryable=true,
                           current_worker_id=NULL,lease_token=NULL,lease_expires_at=NULL
                       WHERE id=%s RETURNING *""",
                    (
                        next_attempt_at,
                        error_code,
                        error_message,
                        delivery_request_id,
                    ),
                ).fetchone()
                event = "delivery_retry_scheduled"
                details = {
                    "error_code": error_code,
                    "next_attempt_at": next_attempt_at.isoformat(),
                    "attempt_count": int(updated["attempt_count"]),
                }
            else:
                updated = conn.execute(
                    """UPDATE football_brief.platform_delivery_requests
                       SET status='failed',completed_at=now(),
                           last_error_code=%s,last_error_message=%s,last_error_retryable=%s,
                           current_worker_id=NULL,lease_token=NULL,lease_expires_at=NULL
                       WHERE id=%s RETURNING *""",
                    (
                        error_code,
                        error_message,
                        retryable,
                        delivery_request_id,
                    ),
                ).fetchone()
                event = "delivery_failed"
                details = {
                    "error_code": error_code,
                    "retryable": retryable,
                    "attempt_count": int(updated["attempt_count"]),
                }
            self._event(
                conn,
                delivery_request_id=delivery_request_id,
                target_id=updated["target_id"],
                event=event,
                actor=worker_id,
                details=details,
            )
        return {
            "ok": False,
            "delivery": dict(updated),
            "retry_scheduled": can_retry,
        }

    def _recover_expired_locked(
        self,
        conn: Any,
        *,
        now: datetime,
        actor: str,
        limit: int,
    ) -> None:
        rows = conn.execute(
            """SELECT * FROM football_brief.platform_delivery_requests
               WHERE status='processing' AND lease_expires_at<=%s
               ORDER BY lease_expires_at,id
               FOR UPDATE SKIP LOCKED LIMIT %s""",
            (now, limit),
        ).fetchall()
        for row in rows:
            can_retry = int(row["attempt_count"]) < int(row["max_attempts"])
            if can_retry:
                updated = conn.execute(
                    """UPDATE football_brief.platform_delivery_requests
                       SET status='retry_wait',next_attempt_at=%s,
                           last_error_code='delivery_lease_expired',
                           last_error_message='The previous delivery worker lease expired.',
                           last_error_retryable=true,
                           current_worker_id=NULL,lease_token=NULL,lease_expires_at=NULL
                       WHERE id=%s RETURNING *""",
                    (now + timedelta(seconds=60), row["id"]),
                ).fetchone()
            else:
                updated = conn.execute(
                    """UPDATE football_brief.platform_delivery_requests
                       SET status='failed',completed_at=%s,
                           last_error_code='delivery_lease_expired',
                           last_error_message='The delivery worker lease expired at the attempt limit.',
                           last_error_retryable=true,
                           current_worker_id=NULL,lease_token=NULL,lease_expires_at=NULL
                       WHERE id=%s RETURNING *""",
                    (now, row["id"]),
                ).fetchone()
            self._event(
                conn,
                delivery_request_id=row["id"],
                target_id=row["target_id"],
                event="delivery_lease_recovered",
                actor=actor,
                details={
                    "new_status": updated["status"],
                    "attempt_count": int(updated["attempt_count"]),
                },
            )

    @staticmethod
    def _rate_limited(conn: Any, target: Mapping[str, Any], *, now: datetime) -> bool:
        counts = conn.execute(
            """SELECT
                   count(*) FILTER (WHERE pda.started_at>%s) AS minute_count,
                   count(*) FILTER (WHERE pda.started_at>%s) AS day_count
               FROM football_brief.platform_delivery_attempts pda
               JOIN football_brief.platform_delivery_requests pdr
                 ON pdr.id=pda.delivery_request_id
               WHERE pdr.target_id=%s""",
            (now - timedelta(minutes=1), now - timedelta(days=1), target["id"]),
        ).fetchone()
        return (
            int(counts["minute_count"]) >= int(target["requests_per_minute"])
            or int(counts["day_count"]) >= int(target["requests_per_day"])
        )

    def _require_target_adapters(self, target: Mapping[str, Any]) -> None:
        if target["execution_enabled"]:
            if target["primary_adapter_key"] not in self.adapters:
                raise PlatformDeliveryError("delivery_primary_adapter_not_configured")
            if target["fallback_adapter_key"] and target["fallback_adapter_key"] not in self.adapters:
                raise PlatformDeliveryError("delivery_fallback_adapter_not_configured")

    def _require_request_adapters(self, request: DeliveryTargetRequest) -> None:
        if request.execution_enabled:
            if request.primary_adapter_key not in self.adapters:
                raise PlatformDeliveryError("delivery_primary_adapter_not_configured")
            if request.fallback_adapter_key and request.fallback_adapter_key not in self.adapters:
                raise PlatformDeliveryError("delivery_fallback_adapter_not_configured")

    @staticmethod
    def _require_active_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]):
            raise PlatformDeliveryError("operator_inactive_or_missing")

    @staticmethod
    def _require_publisher(conn: Any, actor: str) -> None:
        row = conn.execute(
            """SELECT ou.active,EXISTS(
                   SELECT 1 FROM football_brief.operator_user_roles our
                   WHERE our.operator_id=ou.operator_id AND our.role='publisher'
               ) AS is_publisher
               FROM football_brief.operator_users ou WHERE ou.operator_id=%s""",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]) or not bool(row["is_publisher"]):
            raise PlatformDeliveryError("publisher_role_required")

    @staticmethod
    def _target_for_update(conn: Any, target_id: UUID) -> Mapping[str, Any]:
        row = conn.execute(
            "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s FOR UPDATE",
            (target_id,),
        ).fetchone()
        if not row:
            raise PlatformDeliveryError("delivery_target_not_found")
        return row

    @staticmethod
    def _insert_target(
        conn: Any,
        *,
        request: DeliveryTargetRequest,
        version: int,
        parent_id: UUID | None,
        status: str,
        actor: str,
    ) -> Mapping[str, Any]:
        return conn.execute(
            """INSERT INTO football_brief.platform_delivery_targets
               (target_key,version,parent_target_id,display_name,platform,environment,
                primary_adapter_key,fallback_adapter_key,supported_privacy,default_privacy,
                credential_secret_ref,simulated,execution_enabled,requests_per_minute,
                requests_per_day,status,configuration,created_by,activated_by,activated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,
                       CASE WHEN %s='active' THEN now() END)
               RETURNING *""",
            (
                request.target_key,
                version,
                parent_id,
                request.display_name,
                request.platform,
                request.environment,
                request.primary_adapter_key,
                request.fallback_adapter_key,
                [value.value for value in request.supported_privacy],
                request.default_privacy.value,
                request.credential_secret_ref,
                request.simulated,
                request.execution_enabled,
                request.requests_per_minute,
                request.requests_per_day,
                status,
                _json(request.configuration),
                actor,
                actor if status == "active" else None,
                status,
            ),
        ).fetchone()

    @staticmethod
    def _event(
        conn: Any,
        *,
        event: str,
        actor: str,
        details: dict[str, Any],
        delivery_request_id: UUID | None = None,
        target_id: UUID | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.platform_delivery_events
               (delivery_request_id,target_id,event,actor,details)
               VALUES (%s,%s,%s,%s,%s::jsonb)""",
            (
                delivery_request_id,
                target_id,
                event,
                actor,
                _json(details),
            ),
        )
