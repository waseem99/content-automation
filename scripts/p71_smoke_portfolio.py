#!/usr/bin/env python3
"""Read-only staging smoke checks for readiness, authentication, brands, and queue."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def get(base: str, path: str, key: str | None = None) -> tuple[int, dict]:
    headers = {"X-Operator-Key": key} if key else {}
    request = Request(f"{base.rstrip('/')}{path}", headers=headers)
    with urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode())


def main() -> int:
    base = os.getenv("PORTFOLIO_API_URL", "http://127.0.0.1:8000")
    key = os.getenv("OPERATOR_KEY", "").strip()
    if not key:
        raise SystemExit("OPERATOR_KEY is required")
    health_status, health = get(base, "/health")
    ready_status, ready = get(base, "/runtime/ready")
    brands_status, brands = get(base, "/portfolio/brands", key)
    queue_status, queue = get(base, "/portfolio/queue", key)
    assert health_status == 200 and health["ok"]
    assert ready_status == 200 and ready["ok"]
    assert brands_status == 200 and brands["ok"]
    assert queue_status == 200 and queue["ok"]
    print(json.dumps({"ok": True, "brand_count": brands["count"], "queue_count": queue["count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
