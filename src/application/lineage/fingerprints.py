from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def request_fingerprint(*, provider: str, operation: str, model_id: str, prompt_hash: str | None, input_sha256: str | None, parameters: dict | None = None) -> str:
    return sha256_json(
        {
            "provider": provider,
            "operation": operation,
            "model_id": model_id,
            "prompt_hash": prompt_hash,
            "input_sha256": input_sha256,
            "parameters": parameters or {},
        }
    )
