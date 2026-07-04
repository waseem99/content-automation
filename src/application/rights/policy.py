from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class RightsPolicyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RightsPolicy:
    name: str
    version: str
    content_hash: str
    reason_priority: tuple[str, ...]
    supported_platforms: tuple[str, ...]
    review_due_behavior: str
    raw: dict

    def priority(self, reason: str) -> int:
        try:
            return self.reason_priority.index(reason)
        except ValueError:
            return len(self.reason_priority)


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def load_rights_policy(path: Path) -> RightsPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "policy_name",
        "version",
        "reason_priority",
        "supported_platforms",
        "review_due_behavior",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise RightsPolicyError(f"Rights policy is missing fields: {', '.join(missing)}")
    content_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return RightsPolicy(
        name=str(payload["policy_name"]),
        version=str(payload["version"]),
        content_hash=content_hash,
        reason_priority=tuple(str(item) for item in payload["reason_priority"]),
        supported_platforms=tuple(str(item) for item in payload["supported_platforms"]),
        review_due_behavior=str(payload["review_due_behavior"]),
        raw=payload,
    )
