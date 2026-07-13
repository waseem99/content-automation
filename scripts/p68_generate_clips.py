#!/usr/bin/env python3
"""Submit or refresh P68 Wan jobs without holding a long-running process."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

from src.p68_clip_generator import ClipGenerationController, build_requests, load_terms
from src.p68_generation_governance import GenerationBudget
from src.p68_video_provider import ComfyUIVideoProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("health", "submit", "refresh", "status"))
    parser.add_argument("--pilot")
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--workflow", default=os.getenv("P68_RN_WORKFLOW", "deploy/p68-rn-worker/workflows/wan22-ti2v-5b-api.json"))
    parser.add_argument("--model-manifest", default="deploy/p68-rn-worker/model-manifest.json")
    parser.add_argument("--variants", type=int, default=1, help="Variants for standard shots")
    parser.add_argument("--hero-variants", type=int, default=2, help="Variants for hook/reveal shots")
    parser.add_argument("--allow-master-preview", action="store_true")
    parser.add_argument("--shots", help="Comma-separated shot IDs; authored science shots are skipped by default")
    parser.add_argument("--expected-runtime-seconds", type=Decimal, default=Decimal("540"))
    args = parser.parse_args()

    if args.command != "health" and not args.pilot:
        parser.error(f"{args.command} requires --pilot")
    base_url = os.getenv("P68_RN_BASE_URL")
    if not base_url and args.command != "status":
        parser.error("P68_RN_BASE_URL is required")
    provider = ComfyUIVideoProvider(
        base_url=base_url or "http://127.0.0.1:8188",
        bearer_token=os.getenv("P68_RN_BEARER_TOKEN"),
        workflow_path=Path(args.workflow),
    )
    if args.command == "health":
        print(json.dumps(provider.health(), indent=2))
        return 0
    pilot_dir = Path(args.pilots_root) / str(args.pilot)
    artifact_dir = Path(args.artifact_root) / "gold" / str(args.pilot)
    controller = ClipGenerationController(
        pilot_dir=pilot_dir,
        artifact_dir=artifact_dir,
        provider=provider,
        budget=GenerationBudget(
            soft_cap_usd=Decimal(os.getenv("P68_VIDEO_SOFT_CAP_USD", "4.00")),
            hard_cap_usd=Decimal(os.getenv("P68_VIDEO_HARD_CAP_USD", "10.00")),
            rn_gpu_hourly_usd=Decimal(os.getenv("P68_RN_GPU_HOURLY_USD", "0.00")),
        ),
        terms=load_terms(Path(args.model_manifest)),
    )
    if args.command == "submit":
        requests = build_requests(
            pilot_dir,
            artifact_dir,
            variants=args.variants,
            hero_variants=args.hero_variants,
            allow_master_preview=args.allow_master_preview,
            shot_ids={item.strip() for item in args.shots.split(",") if item.strip()} if args.shots else None,
        )
        output = controller.submit_missing(requests, expected_runtime_seconds=args.expected_runtime_seconds)
    elif args.command == "refresh":
        output = controller.refresh()
    else:
        output = controller.status()
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
