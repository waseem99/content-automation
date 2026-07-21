from __future__ import annotations

from typing import Protocol

from src.application.delivery.models import DeliveryAdapterRequest, DeliveryAdapterResult
from src.application.delivery.reconciliation import (
    DeliveryPlatformStatus,
    DeliveryReconciliationResult,
)


class DeliveryAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class PlatformDeliveryAdapter(Protocol):
    adapter_key: str

    def deliver(
        self,
        request: DeliveryAdapterRequest,
        *,
        target: dict,
    ) -> DeliveryAdapterResult:
        ...

    def reconcile(
        self,
        request: DeliveryAdapterRequest,
        *,
        platform_reference: str,
        target: dict,
    ) -> DeliveryReconciliationResult:
        ...


class _SimulatedReconciliationMixin:
    adapter_key: str

    def reconcile(
        self,
        request: DeliveryAdapterRequest,
        *,
        platform_reference: str,
        target: dict,
    ) -> DeliveryReconciliationResult:
        if not platform_reference.startswith("simulated"):
            raise DeliveryAdapterError(
                "simulated_reconciliation_reference_invalid",
                "The platform reference does not belong to a simulated delivery adapter.",
                retryable=False,
            )
        behavior = str((target.get("configuration") or {}).get("reconcile_behavior", "success"))
        if behavior == "unavailable":
            raise DeliveryAdapterError(
                "simulated_reconciliation_unavailable",
                "The simulated platform status endpoint is unavailable.",
                retryable=True,
            )
        if behavior == "fail_terminal":
            raise DeliveryAdapterError(
                "simulated_reconciliation_terminal_failure",
                "The simulated platform status endpoint returned a terminal failure.",
                retryable=False,
            )
        configured_status = (target.get("configuration") or {}).get("reconcile_status")
        default_status = (
            DeliveryPlatformStatus.DRAFT
            if request.metadata.get("delivery_mode") == "draft"
            else DeliveryPlatformStatus.PUBLISHED
        )
        try:
            platform_status = DeliveryPlatformStatus(configured_status or default_status)
        except ValueError as exc:
            raise DeliveryAdapterError(
                "simulated_reconciliation_status_invalid",
                "The simulated reconciliation status is not supported.",
                retryable=False,
            ) from exc
        return DeliveryReconciliationResult(
            platform_status=platform_status,
            response_payload={
                "adapter": self.adapter_key,
                "simulated": True,
                "platform_reference": platform_reference,
                "platform_status": platform_status.value,
                "release_manifest_hash": request.release_manifest_hash,
            },
        )


class SimulatedPrimaryDeliveryAdapter(_SimulatedReconciliationMixin):
    adapter_key = "simulated-primary"

    def deliver(
        self,
        request: DeliveryAdapterRequest,
        *,
        target: dict,
    ) -> DeliveryAdapterResult:
        behavior = str((target.get("configuration") or {}).get("primary_behavior", "success"))
        if behavior == "unsupported":
            raise DeliveryAdapterError(
                "simulated_primary_unsupported",
                "The simulated primary API does not support this controlled request.",
                retryable=False,
            )
        if behavior == "unavailable":
            raise DeliveryAdapterError(
                "simulated_primary_unavailable",
                "The simulated primary API is unavailable.",
                retryable=True,
            )
        if behavior == "fail_retryable":
            raise DeliveryAdapterError(
                "simulated_primary_retryable_failure",
                "The simulated primary API returned a retryable failure.",
                retryable=True,
            )
        if behavior == "fail_terminal":
            raise DeliveryAdapterError(
                "simulated_primary_terminal_failure",
                "The simulated primary API returned a terminal failure.",
                retryable=False,
            )
        reference = (
            f"simulated://{request.platform}/{request.target_key}/"
            f"{request.delivery_fingerprint[:24]}"
        )
        return DeliveryAdapterResult(
            provider_request_id=f"sim-primary:{request.delivery_fingerprint[:32]}",
            platform_reference=reference,
            response_payload={
                "adapter": self.adapter_key,
                "simulated": True,
                "privacy": request.privacy.value,
                "delivery_mode": request.metadata.get("delivery_mode"),
                "release_manifest_hash": request.release_manifest_hash,
                "platform_reference": reference,
            },
        )


class SimulatedFallbackDeliveryAdapter(_SimulatedReconciliationMixin):
    adapter_key = "simulated-fallback"

    def deliver(
        self,
        request: DeliveryAdapterRequest,
        *,
        target: dict,
    ) -> DeliveryAdapterResult:
        behavior = str((target.get("configuration") or {}).get("fallback_behavior", "success"))
        if behavior == "fail_retryable":
            raise DeliveryAdapterError(
                "simulated_fallback_retryable_failure",
                "The simulated fallback transport returned a retryable failure.",
                retryable=True,
            )
        if behavior == "fail_terminal":
            raise DeliveryAdapterError(
                "simulated_fallback_terminal_failure",
                "The simulated fallback transport returned a terminal failure.",
                retryable=False,
            )
        reference = (
            f"simulated+fallback://{request.platform}/{request.target_key}/"
            f"{request.delivery_fingerprint[:24]}"
        )
        return DeliveryAdapterResult(
            provider_request_id=f"sim-fallback:{request.delivery_fingerprint[:32]}",
            platform_reference=reference,
            response_payload={
                "adapter": self.adapter_key,
                "fallback": True,
                "simulated": True,
                "privacy": request.privacy.value,
                "delivery_mode": request.metadata.get("delivery_mode"),
                "release_manifest_hash": request.release_manifest_hash,
                "platform_reference": reference,
            },
        )


def default_delivery_adapters() -> dict[str, PlatformDeliveryAdapter]:
    return {
        "simulated-primary": SimulatedPrimaryDeliveryAdapter(),
        "simulated-fallback": SimulatedFallbackDeliveryAdapter(),
    }
