from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4

from src.application.delivery import service as delivery_service
from src.application.delivery.adapters import default_delivery_adapters
from src.application.delivery.models import (
    DeliveryAdapterRequest,
    DeliveryClaimRequest,
    DeliveryExecuteRequest,
)
from src.application.delivery.service import (
    PlatformDeliveryError,
    PlatformDeliveryService,
)


class OfficialPlatformDeliveryService(PlatformDeliveryService):
    """P97 delivery plus the single reviewed official YouTube execution path."""

    def __init__(self, database: Any, *, adapters: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            database,
            adapters=adapters if adapters is not None else default_delivery_adapters(database),
        )

    @staticmethod
    def _target_is_executable(target: Mapping[str, Any]) -> bool:
        if target["status"] != "active" or not bool(target["execution_enabled"]):
            return False
        if bool(target["simulated"]):
            return True
        return bool(
            target["primary_adapter_key"] == "youtube-official"
            and target["platform"] == "youtube"
            and target["credential_secret_ref"]
            and target["environment"] in {"staging", "production"}
        )

    def claim_due(
        self,
        request: DeliveryClaimRequest,
        *,
        allowed_brand_ids: Iterable[UUID] | None,
    ) -> dict[str, Any] | None:
        now = delivery_service._utcnow()
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
                """(
                    pdt.simulated=true
                    OR (
                        pdt.primary_adapter_key='youtube-official'
                        AND pdt.platform='youtube'
                        AND pdt.credential_secret_ref IS NOT NULL
                        AND pdt.environment IN ('staging','production')
                    )
                )""",
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
                if not self._target_is_executable(target):
                    continue
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
        if not self._target_is_executable(target):
            raise PlatformDeliveryError("delivery_target_no_longer_executable")
        if target["primary_adapter_key"] not in self.adapters:
            raise PlatformDeliveryError("delivery_primary_adapter_not_configured")
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
