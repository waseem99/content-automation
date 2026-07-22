from __future__ import annotations

import json
import logging
from typing import Any

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
)
from src.application.generation_jobs.service import GenerationJobService


_LOGGER = logging.getLogger("content_automation.worker")


def _log(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    _LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


class ObservedGenerationJobService(GenerationJobService):
    """Adds safe structured worker logs without changing queue state semantics."""

    def claim(self, **kwargs: Any) -> dict[str, Any] | None:
        result = super().claim(**kwargs)
        if result is not None:
            _log(
                "generation_job_claimed",
                job_id=result["job"]["id"],
                attempt_id=result["attempt"]["id"],
                worker_id=result["attempt"]["worker_id"],
                job_type=result["job"]["job_type"],
                provider=result["job"]["provider"],
                attempt_number=result["attempt"]["attempt_number"],
                lease_expires_at=result["attempt"]["lease_expires_at"],
            )
        return result

    def heartbeat(self, request: GenerationJobHeartbeat) -> dict[str, Any]:
        result = super().heartbeat(request)
        _log(
            "generation_job_heartbeat",
            job_id=request.job_id,
            attempt_id=request.attempt_id,
            worker_id=request.worker_id,
            lease_expires_at=result["lease_expires_at"],
        )
        return result

    def complete(self, request: GenerationJobCompletion) -> dict[str, Any]:
        result = super().complete(request)
        _log(
            "generation_job_succeeded",
            job_id=request.job_id,
            attempt_id=request.attempt_id,
            worker_id=request.worker_id,
            provider_request_id=request.provider_request_id,
            actual_cost_usd=request.actual_cost_usd,
            output_fingerprint=result["job"]["output_fingerprint"],
        )
        return result

    def fail(self, request: GenerationJobFailure) -> dict[str, Any]:
        result = super().fail(request)
        _log(
            "generation_job_failed",
            job_id=request.job_id,
            attempt_id=request.attempt_id,
            worker_id=request.worker_id,
            error_code=request.error_code,
            retryable=request.retryable,
            dead_lettered=result["dead_lettered"],
            actual_cost_usd=request.actual_cost_usd,
        )
        return result

    def retry(self, *, job_id, actor: str, delay_seconds: int = 0) -> dict[str, Any]:
        result = super().retry(job_id=job_id, actor=actor, delay_seconds=delay_seconds)
        _log(
            "generation_job_retried",
            job_id=job_id,
            worker_id=actor,
            available_at=result["job"]["available_at"],
        )
        return result

    def cancel(self, *, job_id, actor: str, reason: str) -> dict[str, Any]:
        result = super().cancel(job_id=job_id, actor=actor, reason=reason)
        _log(
            "generation_job_cancelled",
            job_id=job_id,
            worker_id=actor,
            reason_length=len(reason.strip()),
        )
        return result

    def recover_stale(self, *, actor: str, limit: int = 100) -> dict[str, Any]:
        result = super().recover_stale(actor=actor, limit=limit)
        _log(
            "generation_jobs_recovered",
            worker_id=actor,
            recovered=result.get("recovered", 0),
            dead_lettered=result.get("dead_lettered", 0),
        )
        return result
