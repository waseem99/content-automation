#!/usr/bin/env python3
"""Run authorized Facebook discovery/analysis for configured active portfolio brands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "reference-engine"
sys.path.insert(0, str(ENGINE))

from refintel.facebook import run_facebook_page_batch  # noqa: E402
from refintel.models import RightsDeclaration  # noqa: E402
from refintel.settings import RefIntelSettings  # noqa: E402


def configured_pages(
    config_path: Path, selected_brands: set[str]
) -> list[dict[str, str]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pages: list[dict[str, str]] = []
    for brand in config["brands"]:
        if selected_brands and brand["slug"] not in selected_brands:
            continue
        status = brand.get("metadata", {}).get("onboarding_status")
        facebook_links = [
            link
            for link in brand.get("source_links", [])
            if "facebook.com" in link.lower()
        ]
        if status in {"active", "active_research_pending"} and facebook_links:
            pages.append({"brand": brand["slug"], "page_url": facebook_links[0]})
    return pages


def main() -> int:
    settings = RefIntelSettings.from_env()
    default_workspace = (
        settings.workspace if os.getenv("REFINTEL_WORKSPACE") else ENGINE / "workspace"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "portfolio-brands.staging.json",
    )
    parser.add_argument("--workspace", type=Path, default=default_workspace)
    parser.add_argument(
        "--browser-profile",
        type=Path,
        default=settings.facebook_profile,
    )
    parser.add_argument(
        "--rights",
        choices=[item.value for item in RightsDeclaration],
        required=True,
    )
    parser.add_argument("--brand", action="append", default=[])
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument("--acquire-only", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--no-local-vision", action="store_true")
    parser.add_argument("--transcription-model", default="small")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        raise SystemExit("--limit must be between 1 and 100")

    pages = configured_pages(args.config, set(args.brand))
    if not pages:
        raise SystemExit("No active Facebook brands matched the configuration")
    results = []
    rights = RightsDeclaration(args.rights)
    for page in pages:
        try:
            payload = run_facebook_page_batch(
                page["page_url"],
                brand=page["brand"],
                rights=rights,
                workspace_root=args.workspace,
                profile_dir=args.browser_profile,
                limit=args.limit,
                headless=not args.headed,
                discover_only=args.discover_only,
                acquire_only=args.acquire_only,
                use_local_vision=not args.no_local_vision,
                transcription_model=args.transcription_model,
            )
            results.append(
                {
                    **page,
                    "status": "completed",
                    "summary": payload["summary"],
                    "run_dir": payload["run_dir"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - isolate brand failures
            error = str(exc).replace(str(args.browser_profile), "<browser-profile>")
            results.append({**page, "status": "failed", "error": error[:1200]})
    summary = {
        "brand_count": len(results),
        "completed": sum(item["status"] == "completed" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return int(summary["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
