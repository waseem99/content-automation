from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class RendererAdapterStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RendererSubmission:
    provider_request_id: str
    status: RendererAdapterStatus
    request_fingerprint: str
    output_descriptor: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class RendererAdapter(Protocol):
    key: str
    external_fee_possible: bool

    def health(self) -> dict[str, Any]: ...

    def submit(self, request_payload: dict[str, Any]) -> RendererSubmission: ...

    def poll(self, submission: RendererSubmission) -> RendererSubmission: ...

    def cancel(self, submission: RendererSubmission) -> RendererSubmission: ...


def request_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SimulatedRendererAdapter:
    """Deterministic CI adapter. It performs no network or paid operation."""

    key = "simulated"
    external_fee_possible = False

    def health(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "provider": self.key,
            "adapter": "simulated",
            "external_fee_possible": False,
        }

    def submit(self, request_payload: dict[str, Any]) -> RendererSubmission:
        fingerprint = request_fingerprint(request_payload)
        fail = bool(request_payload.get("simulate_failure"))
        if fail:
            return RendererSubmission(
                provider_request_id=f"sim-fail-{fingerprint[:20]}",
                status=RendererAdapterStatus.FAILED,
                request_fingerprint=fingerprint,
                error_code="simulated_failure",
                error_message="Deterministic simulated renderer failure",
            )
        return RendererSubmission(
            provider_request_id=f"sim-{fingerprint[:24]}",
            status=RendererAdapterStatus.QUEUED,
            request_fingerprint=fingerprint,
        )

    def poll(self, submission: RendererSubmission) -> RendererSubmission:
        if submission.status in {
            RendererAdapterStatus.FAILED,
            RendererAdapterStatus.CANCELLED,
            RendererAdapterStatus.SUCCEEDED,
        }:
            return submission
        return RendererSubmission(
            provider_request_id=submission.provider_request_id,
            status=RendererAdapterStatus.SUCCEEDED,
            request_fingerprint=submission.request_fingerprint,
            output_descriptor={
                "kind": "simulated_video",
                "uri": f"simulated://{submission.provider_request_id}.mp4",
                "external_fee_incurred": False,
            },
        )

    def cancel(self, submission: RendererSubmission) -> RendererSubmission:
        return RendererSubmission(
            provider_request_id=submission.provider_request_id,
            status=RendererAdapterStatus.CANCELLED,
            request_fingerprint=submission.request_fingerprint,
        )
