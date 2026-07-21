from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID
from zoneinfo import ZoneInfo

from src.application.delivery.adapters import DeliveryAdapterError
from src.application.delivery.models import (
    DeliveryAdapterRequest,
    DeliveryCreateRequest,
    DeliveryExecuteRequest,
)
from src.application.delivery.service import PlatformDeliveryError, PlatformDeliveryService, _json


class ValidatedPlatformDeliveryService(PlatformDeliveryService):
    """Publisher-only simulated delivery with fail-closed release and media checks."""

    @staticmethod
    def _require_publisher(conn: Any, actor: str) -> None:
        row = conn.execute(
            """SELECT ou.active,EXISTS(
                   SELECT 1 FROM football_brief.operator_user_roles our
                   WHERE our.operator_user_id=ou.id AND our.role='publisher'
               ) AS is_publisher
               FROM football_brief.operator_users ou WHERE ou.operator_id=%s""",
            (actor,),
        ).fetchone()
        if not row or not bool(row["active"]) or not bool(row["is_publisher"]):
            raise PlatformDeliveryError("publisher_role_required")

    def create_delivery(
        self,
        request: DeliveryCreateRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            release = conn.execute(
                """SELECT fr.*,mp.brand_id
                   FROM football_brief.final_releases fr
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE fr.id=%s""",
                (request.final_release_id,),
            ).fetchone()
            target = conn.execute(
                "SELECT * FROM football_brief.platform_delivery_targets WHERE id=%s",
                (request.target_id,),
            ).fetchone()
            if not release:
                raise PlatformDeliveryError("final_release_not_found")
            if release["status"] != "approved" or not release["manifest_hash"] or not release["release_manifest"]:
                raise PlatformDeliveryError(
                    "delivery_release_not_approved",
                    details={"status": release["status"]},
                )
            if not target:
                raise PlatformDeliveryError("delivery_target_not_found")

            configuration = dict(target["configuration"] or {})
            contract = dict(configuration.get("content_contract") or {})
            if len(request.title) > int(contract.get("title_max_length", 0)):
                raise PlatformDeliveryError("delivery_title_exceeds_target_limit")
            if len(request.caption) > int(contract.get("caption_max_length", 0)):
                raise PlatformDeliveryError("delivery_caption_exceeds_target_limit")
            if len(request.hashtags) > int(contract.get("hashtag_limit", -1)):
                raise PlatformDeliveryError("delivery_hashtags_exceed_target_limit")
            if bool(contract.get("disclosure_required")) and not request.disclosure_text:
                raise PlatformDeliveryError("delivery_disclosure_required")
            if bool(contract.get("thumbnail_required")) and request.thumbnail_artifact_version_id is None:
                raise PlatformDeliveryError("delivery_thumbnail_required")

            if request.thumbnail_artifact_version_id is not None:
                thumbnail = conn.execute(
                    """SELECT sav.id
                       FROM football_brief.shared_artifact_versions sav
                       WHERE sav.id=%s
                         AND sav.brand_id=%s
                         AND sav.portfolio_content_id=%s
                         AND sav.content_version=%s
                         AND sav.artifact_kind='thumbnail'
                         AND sav.status='current'
                         AND EXISTS (
                             SELECT 1
                             FROM football_brief.shared_artifact_object_roles saor
                             JOIN football_brief.shared_storage_objects sso
                               ON sso.id=saor.storage_object_id
                             WHERE saor.artifact_version_id=sav.id
                               AND saor.role IN ('original','thumbnail')
                               AND sso.status='available'
                         )""",
                    (
                        request.thumbnail_artifact_version_id,
                        release["brand_id"],
                        release["portfolio_content_id"],
                        release["content_version"],
                    ),
                ).fetchone()
                if not thumbnail:
                    raise PlatformDeliveryError("delivery_thumbnail_not_current_or_available")

            target_account_ref = str(configuration.get("target_account_ref", "")).strip()
            target_time_zone = str(configuration.get("time_zone", "")).strip()
            if not target_account_ref or not target_time_zone:
                raise PlatformDeliveryError("delivery_target_account_or_time_zone_missing")
            scheduled_local = (
                request.scheduled_for.astimezone(ZoneInfo(target_time_zone)).isoformat()
                if request.scheduled_for is not None
                else None
            )

        metadata = dict(request.metadata)
        metadata.update(
            {
                "target_account_ref": target_account_ref,
                "target_time_zone": target_time_zone,
                "scheduled_for_local": scheduled_local,
            }
        )
        canonical_request = request.model_copy(update={"metadata": metadata})
        return super().create_delivery(canonical_request, actor=actor)

    def execute_claim(self, request: DeliveryExecuteRequest) -> dict[str, Any]:
        with self.database.connection() as conn:
            existing = conn.execute(
                "SELECT status FROM football_brief.platform_delivery_requests WHERE id=%s",
                (request.delivery_request_id,),
            ).fetchone()
        if not existing:
            raise PlatformDeliveryError("delivery_request_not_found")
        if existing["status"] == "succeeded":
            detail = self.detail(delivery_request_id=request.delivery_request_id)
            return {**detail, "reused": True}
        if existing["status"] in {"failed", "cancelled"}:
            raise PlatformDeliveryError(
                "delivery_request_terminal",
                details={"status": existing["status"]},
            )
        return super().execute_claim(request)

    def _claimed_context_for_update(
        self,
        conn: Any,
        *,
        request: DeliveryExecuteRequest,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], DeliveryAdapterRequest]:
        delivery, target, adapter_request = super()._claimed_context_for_update(conn, request=request)
        available = conn.execute(
            """SELECT count(*) AS count
               FROM football_brief.shared_artifact_object_roles saor
               JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
               WHERE saor.artifact_version_id=%s
                 AND saor.role='original'
                 AND sso.status='available'""",
            (adapter_request.output_artifact_version_id,),
        ).fetchone()["count"]
        if int(available) != 1:
            raise PlatformDeliveryError("delivery_release_output_unavailable")
        return delivery, target, adapter_request

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
            adapter_request = self._adapter_request_for_delivery(conn, delivery=delivery, target=target)

        if not target["simulated"]:
            raise PlatformDeliveryError("p97_live_reconciliation_disabled")
        adapter_key = attempt["adapter_key"] if attempt else target["primary_adapter_key"]
        adapter = self.adapters.get(adapter_key)
        if adapter is None:
            raise PlatformDeliveryError("delivery_reconciliation_adapter_not_configured")
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

    def detail(self, *, delivery_request_id: UUID) -> dict[str, Any]:
        result = super().detail(delivery_request_id=delivery_request_id)
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.platform_delivery_reconciliations
                   WHERE delivery_request_id=%s ORDER BY sequence_number""",
                (delivery_request_id,),
            ).fetchall()
        result["reconciliations"] = [dict(row) for row in rows]
        return result

    @staticmethod
    def _adapter_request_for_delivery(
        conn: Any,
        *,
        delivery: Mapping[str, Any],
        target: Mapping[str, Any],
    ) -> DeliveryAdapterRequest:
        release = conn.execute(
            "SELECT * FROM football_brief.final_releases WHERE id=%s",
            (delivery["final_release_id"],),
        ).fetchone()
        output = conn.execute(
            """SELECT sav.id,a.sha256
               FROM football_brief.shared_artifact_versions sav
               JOIN football_brief.assets a ON a.id=sav.original_asset_id
               WHERE sav.id=%s""",
            (release["output_artifact_version_id"],),
        ).fetchone()
        return DeliveryAdapterRequest(
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
