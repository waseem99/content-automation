from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.delivery.adapters import DeliveryAdapterError
from src.application.delivery.official_service import OfficialPlatformDeliveryService
from src.application.delivery.service import PlatformDeliveryError, _json
from src.application.delivery.validated_service import ValidatedPlatformDeliveryService


class OfficialValidatedPlatformDeliveryService(
    ValidatedPlatformDeliveryService,
    OfficialPlatformDeliveryService,
):
    """Validated simulated delivery plus one official YouTube adapter."""

    def reconcile_delivery(
        self,
        *,
        delivery_request_id: UUID,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            self._require_publisher(conn, actor)
            delivery = conn.execute(
                "SELECT * FROM football_brief.platform_delivery_requests WHERE id=%s",
                (delivery_request_id,),
            ).fetchone()
            if not delivery:
                raise PlatformDeliveryError("delivery_request_not_found")
            if delivery["status"] != "succeeded" or not delivery["platform_reference"]:
                raise PlatformDeliveryError(
                    "delivery_not_ready_for_reconciliation",
                    details={"status": delivery["status"]},
                )
            target = conn.execute(
                "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s",
                (delivery["target_id"],),
            ).fetchone()
            attempt = conn.execute(
                """SELECT adapter_key FROM football_brief.platform_delivery_attempts
                   WHERE delivery_request_id=%s AND status='succeeded'
                   ORDER BY sequence_number DESC LIMIT 1""",
                (delivery_request_id,),
            ).fetchone()
            adapter_request = self._adapter_request_for_delivery(
                conn,
                delivery=delivery,
                target=target,
            )

        adapter_key = attempt["adapter_key"] if attempt else target["primary_adapter_key"]
        adapter = self.adapters.get(adapter_key)
        if adapter is None:
            raise PlatformDeliveryError("delivery_reconciliation_adapter_not_configured")
        if not bool(target["simulated"]) and adapter_key != "youtube-official":
            raise PlatformDeliveryError("delivery_live_adapter_not_approved")
        try:
            result = adapter.reconcile(
                adapter_request,
                platform_reference=delivery["platform_reference"],
                target=dict(target),
            )
        except DeliveryAdapterError as exc:
            raise PlatformDeliveryError(
                "delivery_reconciliation_failed",
                details={
                    "adapter_error": exc.code,
                    "retryable": exc.retryable,
                },
            ) from exc

        with self.database.transaction() as conn:
            self._require_publisher(conn, actor)
            current = conn.execute(
                "SELECT * FROM football_brief.platform_delivery_requests WHERE id=%s FOR UPDATE",
                (delivery_request_id,),
            ).fetchone()
            if current["status"] != "succeeded" or current["platform_reference"] != delivery["platform_reference"]:
                raise PlatformDeliveryError("delivery_reconciliation_state_changed")
            sequence = int(
                conn.execute(
                    """SELECT COALESCE(max(sequence_number),0)+1 AS sequence
                       FROM football_brief.platform_delivery_reconciliations
                       WHERE delivery_request_id=%s""",
                    (delivery_request_id,),
                ).fetchone()["sequence"]
            )
            reconciliation = conn.execute(
                """INSERT INTO football_brief.platform_delivery_reconciliations
                   (delivery_request_id,sequence_number,adapter_key,platform_reference,
                    platform_status,response_payload,reconciled_by)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                (
                    delivery_request_id,
                    sequence,
                    adapter_key,
                    current["platform_reference"],
                    result.platform_status.value,
                    _json(result.response_payload),
                    actor,
                ),
            ).fetchone()
        return {
            "ok": True,
            "delivery": dict(current),
            "reconciliation": dict(reconciliation),
        }
