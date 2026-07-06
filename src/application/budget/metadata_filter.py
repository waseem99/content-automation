from __future__ import annotations

from typing import Any


MASK = "[redacted]"
KEY_FRAGMENTS = ("credential", "access", "private", "password", "bearer")


def scrub_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in KEY_FRAGMENTS):
                cleaned[key] = MASK
            else:
                cleaned[key] = scrub_metadata(item)
        return cleaned
    if isinstance(value, list):
        return [scrub_metadata(item) for item in value]
    return value
