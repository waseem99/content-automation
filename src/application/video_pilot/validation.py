from __future__ import annotations

import re
from typing import Any


_SENSITIVE_FIELD = re.compile(
    r"(password|secret|token|cookie|operator.?key|api.?key|authorization)",
    re.IGNORECASE,
)


class PilotSnapshotValidationError(ValueError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


def assert_snapshot_safe(value: Any, *, path: str = "snapshot") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if _SENSITIVE_FIELD.search(str(key)):
                raise PilotSnapshotValidationError(child)
            assert_snapshot_safe(item, path=child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_snapshot_safe(item, path=f"{path}[{index}]")
