from __future__ import annotations

from typing import Protocol

from src.application.delivery.models import DeliveryAdapterRequest, DeliveryAdapterResult


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


class SimulatedPrimaryDeliveryAdapter:
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
                "release_manifest_hash": request.release_manifest_hash,
                "platform_reference": reference,
            },
        )


class SimulatedFallbackDeliveryAdapter:
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
                "release_manifest_hash": request.release_manifest_hash,
                "platform_reference": reference,
            },
        )


def default_delivery_adapters() -> dict[str, PlatformDeliveryAdapter]:
    return {
        "simulated-primary": SimulatedPrimaryDeliveryAdapter(),
        "simulated-fallback": SimulatedFallbackDeliveryAdapter(),
    }
