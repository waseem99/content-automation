from __future__ import annotations

import re
from typing import Any


MASK = "[redacted]"
SENSITIVE_KEY_PARTS = ("credential", "secret", "password", "token", "authorization", "bearer")
SENSITIVE_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
)


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: MASK if _sensitive_key(key) else redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        cleaned = value
        for pattern in SENSITIVE_PATTERNS:
            cleaned = pattern.sub(MASK, cleaned)
        return cleaned
    return value


def _sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
