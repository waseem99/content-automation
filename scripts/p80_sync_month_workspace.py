#!/usr/bin/env python3
"""Idempotently sync generated month packages into the existing PostgreSQL operator API."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path


def request(base: str, key: str, method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}", data=body, method=method,
        headers={"X-Operator-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310 - operator URL is explicit
        return json.loads(response.read().decode())


def workspace_payload(item: dict) -> dict:
    return {
        "script": item["script"], "scene_plan": {"scenes": item["scene_plan"]},
        "voiceover": item["voice"], "premium_budget_usd": None,
        "metadata": {
            "p80_content_fingerprint": item["content_fingerprint"],
            "thumbnail": item["thumbnail"], "platform_packages": item["platform_packages"],
            "production": item["production"], "month_batch": item["batch"],
            "scheduled_time_local": item.get("scheduled_time_local"),
            "daily_slot": item.get("daily_slot"),
            "editorial_angle": item.get("editorial_angle"),
            "production_tier": item.get("production_tier"),
            "source_title": item.get("source_title"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    parser.add_argument("--api", default=os.getenv("OPERATOR_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--key", default=os.getenv("OPERATOR_KEY"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    studio = json.loads(args.studio.read_text(encoding="utf-8"))
    if args.dry_run:
        print(json.dumps({"brand": studio["brand"]["slug"], "packages": len(studio["items"]), "writes": 0}))
        return 0
    if not args.key:
        raise SystemExit("OPERATOR_KEY is required")
    queue = request(args.api, args.key, "GET", "/portfolio/queue")
    by_title = {item["title"]: item for item in queue["items"] if item.get("brand_slug") == studio["brand"]["slug"]}
    updated, missing = [], []
    for item in studio["items"]:
        target = by_title.get(item["title"])
        if not target:
            missing.append(item["title"])
            continue
        request(args.api, args.key, "POST", f"/portfolio/content/{target['id']}/workspace", workspace_payload(item))
        updated.append(target["id"])
    print(json.dumps({"updated": len(updated), "missing": missing}, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
