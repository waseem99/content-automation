#!/usr/bin/env python3
"""Idempotently onboard brands, monthly plans, and reviewable planning inventory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base_url: str, operator_key: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json", "X-Operator-Key": operator_key},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/portfolio-brands.staging.json"))
    parser.add_argument("--api-url", default=os.getenv("PORTFOLIO_API_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    operator_key = os.getenv("OPERATOR_KEY", "").strip()
    if not operator_key:
        raise SystemExit("OPERATOR_KEY is required; do not put it in the JSON config")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    results = []
    for brand in config["brands"]:
        created = call(args.api_url, operator_key, "/portfolio/brands", brand)
        brand_record = created["brand"]
        plan = call(
            args.api_url,
            operator_key,
            "/portfolio/plans",
            {
                "brand_id": brand_record["id"],
                "month_start": config["month_start"],
                "target_count": brand["monthly_target"],
                "strategy": {
                    "primary_platform": brand["primary_platform"],
                    "content_pillars": brand["content_pillars"],
                    "human_approval_required": True,
                    "automatic_publishing": False,
                },
            },
        )
        created_count = 0
        duplicate_count = 0
        for idea in brand.get("ideas", []):
            content = call(
                args.api_url,
                operator_key,
                "/portfolio/content",
                {
                    "plan_id": plan["plan"]["id"],
                    "brand_slug": brand_record["slug"],
                    "scheduled_for": idea["scheduled_for"],
                    "title": idea["title"],
                    "concept": idea["concept"],
                    "format_name": idea["format_name"],
                },
            )
            created_count += int(content.get("ok") is True)
            duplicate_count += int(content.get("duplicate") is True)
        results.append(
            {
                "brand": brand_record["slug"],
                "plan_id": plan["plan"]["id"],
                "inventory_created": created_count,
                "inventory_duplicates_skipped": duplicate_count,
                "onboarding_status": brand.get("metadata", {}).get("onboarding_status", "unknown"),
            }
        )
    readiness = call(
        args.api_url,
        operator_key,
        f"/portfolio/readiness?month_start={config['month_start']}",
    )
    print(json.dumps({"ok": True, "count": len(results), "items": results, "readiness": readiness}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
