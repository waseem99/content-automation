from __future__ import annotations

import hashlib
import json
from typing import Any

from src.application.workers.models import WorkerDefinition


REDACTED = "__excluded__"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_worker_payload(definition: WorkerDefinition, input_payload: dict[str, Any]) -> dict[str, Any]:
    if definition.idempotency_fields:
        scoped_input = {key: input_payload.get(key) for key in definition.idempotency_fields}
    else:
        scoped_input = dict(input_payload)
    for secret_key in ("api_key", "token", "authorization", "password", "secret"):
        if secret_key in scoped_input:
            scoped_input[secret_key] = REDACTED
    return {
        "worker": definition.name,
        "worker_version": definition.version,
        "input_schema": definition.input_schema_name,
        "input_schema_version": definition.input_schema_version,
        "output_schema": definition.output_schema_name,
        "output_schema_version": definition.output_schema_version,
        "input": scoped_input,
    }


def worker_input_hash(definition: WorkerDefinition, input_payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(canonical_worker_payload(definition, input_payload)))


def worker_idempotency_key(definition: WorkerDefinition, input_payload: dict[str, Any]) -> str:
    return f"worker:{definition.name}:{definition.version}:{worker_input_hash(definition, input_payload)}"


def output_hash(output: dict[str, Any]) -> str:
    return sha256_text(canonical_json(output))
