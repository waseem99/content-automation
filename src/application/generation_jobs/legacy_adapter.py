from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from src.application.generation_jobs.models import (
    GenerationJobEnqueue,
    LegacyGenerationRecord,
)
from src.application.generation_jobs.service import GenerationJobService


TERMINAL_LEGACY_STATUSES = {
    "succeeded",
    "success",
    "complete",
    "completed",
    "failed",
    "error",
    "cancelled",
    "canceled",
    "dead_letter",
}


class LegacyLedgerError(ValueError):
    pass


def load_legacy_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise LegacyLedgerError(f"Legacy ledger does not exist: {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        records = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LegacyLedgerError(f"Invalid JSON on line {line_number}") from exc
            if not isinstance(value, dict):
                raise LegacyLedgerError(f"Legacy line {line_number} must contain an object")
            records.append(value)
        return records
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyLedgerError("Legacy ledger is not valid JSON") from exc
    if isinstance(value, dict):
        if isinstance(value.get("jobs"), list):
            value = value["jobs"]
        else:
            value = [value]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise LegacyLedgerError("Legacy JSON must contain an object, a list of objects, or a jobs list")
    return list(value)


def normalize_legacy_record(raw: dict[str, Any], *, index: int) -> LegacyGenerationRecord:
    legacy_id = raw.get("legacy_id") or raw.get("job_id") or raw.get("id") or raw.get("key")
    if legacy_id is None:
        legacy_id = f"record-{index}-{_stable_short_hash(raw)}"
    status = raw.get("status") or raw.get("state") or raw.get("outcome") or "queued"
    input_payload = raw.get("input_payload") or raw.get("inputs") or raw.get("input") or raw.get("request") or {}
    output_payload = raw.get("output_payload") or raw.get("outputs") or raw.get("output") or raw.get("result")
    if not isinstance(input_payload, dict):
        input_payload = {"legacy_value": input_payload}
    if output_payload is not None and not isinstance(output_payload, dict):
        output_payload = {"legacy_value": output_payload}
    actual_cost = raw.get("actual_cost_usd", raw.get("cost_usd", raw.get("cost", 0)))
    attempts = raw.get("attempt_count", raw.get("attempts", raw.get("attempt", 1)))
    if isinstance(attempts, list):
        attempts = len(attempts)
    metadata = dict(raw.get("metadata") or {})
    metadata.update(
        {
            "legacy_created_at": raw.get("created_at"),
            "legacy_updated_at": raw.get("updated_at"),
            "legacy_path": raw.get("path") or raw.get("output_path"),
            "retryable": bool(raw.get("retryable", metadata.get("retryable", False))),
        }
    )
    return LegacyGenerationRecord(
        legacy_id=str(legacy_id),
        status=str(status),
        job_type=raw.get("job_type") or raw.get("type") or "keyframe",
        provider=raw.get("provider") or "p68-local",
        model_id=raw.get("model_id") or raw.get("model"),
        worker_id=raw.get("worker_id") or raw.get("worker"),
        input_payload=input_payload,
        output_payload=output_payload,
        error_code=raw.get("error_code"),
        error_message=raw.get("error_message") or raw.get("error"),
        actual_cost_usd=actual_cost or 0,
        attempt_count=max(0, int(attempts or 0)),
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def import_legacy_ledger(
    *,
    service: GenerationJobService,
    path: Path,
    content_id: UUID,
    content_version: int,
    actor: str,
    source_name: str = "p68-file-ledger",
) -> dict[str, Any]:
    raw_records = load_legacy_records(path)
    return import_legacy_records(
        service=service,
        records=(normalize_legacy_record(raw, index=index) for index, raw in enumerate(raw_records, start=1)),
        content_id=content_id,
        content_version=content_version,
        actor=actor,
        source_name=source_name,
    )


def import_legacy_records(
    *,
    service: GenerationJobService,
    records: Iterable[LegacyGenerationRecord],
    content_id: UUID,
    content_version: int,
    actor: str,
    source_name: str,
) -> dict[str, Any]:
    imported = 0
    reused = 0
    recovered_to_queue = 0
    job_ids: list[str] = []
    for record in records:
        status = record.status.strip().lower()
        if status in TERMINAL_LEGACY_STATUSES:
            result = service.import_legacy_terminal(
                content_id=content_id,
                content_version=content_version,
                source_name=source_name,
                record=record,
                actor=actor,
            )
        else:
            result = service.enqueue(
                GenerationJobEnqueue(
                    portfolio_content_id=content_id,
                    content_version=content_version,
                    job_type=record.job_type,
                    provider=record.provider,
                    model_id=record.model_id,
                    preferred_worker_id=record.worker_id,
                    idempotency_key=f"legacy:{source_name}:{record.legacy_id}",
                    input_payload=record.input_payload,
                    max_attempts=max(3, min(10, record.attempt_count + 1)),
                    legacy_source={
                        "source": source_name,
                        "legacy_id": record.legacy_id,
                        "imported_status": status,
                        "metadata": record.metadata,
                        "recovered_after_restart": status in {"running", "processing", "claimed"},
                    },
                ),
                actor=actor,
            )
            if status in {"running", "processing", "claimed"}:
                recovered_to_queue += 1
        if result.get("reused"):
            reused += 1
        else:
            imported += 1
        job_ids.append(str(result["id"]))
    return {
        "ok": True,
        "record_count": imported + reused,
        "imported": imported,
        "reused": reused,
        "recovered_to_queue": recovered_to_queue,
        "job_ids": job_ids,
    }


def _stable_short_hash(value: Any) -> str:
    import hashlib

    encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
