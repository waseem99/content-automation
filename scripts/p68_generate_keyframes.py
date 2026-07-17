#!/usr/bin/env python3
"""Dry-run, submit, refresh, or inspect bounded P68 keyframe jobs."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

from src.p68_keyframe_generator import KeyframeGenerationController, build_keyframe_requests
from src.p68_keyframe_provider import ComfyUIKeyframeProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "health", "submit", "refresh", "status"))
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--pilot")
    parser.add_argument("--shots")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--runtime-seconds", type=Decimal, default=Decimal("120"))
    parser.add_argument("--width", type=int, default=int(os.getenv("P68_KEYFRAME_WIDTH", "1024")))
    parser.add_argument("--height", type=int, default=int(os.getenv("P68_KEYFRAME_HEIGHT", "1824")))
    parser.add_argument("--workflow", default="deploy/p68-rn-worker/workflows/sdxl-keyframe-api.json")
    args = parser.parse_args()
    pilots_root, artifact_root = Path(args.pilots_root), Path(args.artifact_root)
    requests = build_keyframe_requests(
        pilots_root,
        artifact_root,
        pilot_id=args.pilot,
        shot_ids={item.strip() for item in args.shots.split(",") if item.strip()} if args.shots else None,
        width=args.width,
        height=args.height,
    )
    if args.command == "plan":
        print(json.dumps({
            "schema_version": "p68.keyframe_generation_plan.v2",
            "request_count": len(requests),
            "canvas": {"width": args.width, "height": args.height, "orientation": "portrait"},
            "requests": [
                {
                    "pilot_id": item.pilot_id,
                    "shot_id": item.shot_id,
                    "seed": item.seed,
                    "width": item.width,
                    "height": item.height,
                    "idempotency_key": item.idempotency_key,
                }
                for item in requests
            ],
            "provider_calls_made": 0,
            "vercel_deployment_required": False,
            "publish_allowed": False,
        }, indent=2))
        return 0
    base_url = os.getenv("P68_KEYFRAME_BASE_URL") or os.getenv("P68_RN_BASE_URL")
    checkpoint = os.getenv("P68_KEYFRAME_CHECKPOINT")
    license_type = os.getenv("P68_KEYFRAME_MODEL_LICENSE_TYPE")
    license_url = os.getenv("P68_KEYFRAME_MODEL_LICENSE_URL")
    if not all((base_url, checkpoint, license_type, license_url)):
        parser.error("provider commands require P68_KEYFRAME_BASE_URL (or P68_RN_BASE_URL), P68_KEYFRAME_CHECKPOINT, P68_KEYFRAME_MODEL_LICENSE_TYPE, and P68_KEYFRAME_MODEL_LICENSE_URL")
    provider = ComfyUIKeyframeProvider(
        base_url=base_url,
        workflow_path=Path(args.workflow),
        checkpoint=checkpoint,
        bearer_token=os.getenv("P68_KEYFRAME_BEARER_TOKEN") or os.getenv("P68_RN_BEARER_TOKEN"),
    )
    if args.command == "health":
        print(json.dumps(provider.health(), indent=2))
        return 0
    controller = KeyframeGenerationController(
        pilots_root=pilots_root,
        artifact_root=artifact_root,
        provider=provider,
        checkpoint=checkpoint,
        license_type=license_type,
        license_url=license_url,
        gpu_hourly_usd=Decimal(os.getenv("P68_KEYFRAME_GPU_HOURLY_USD", os.getenv("P68_RN_GPU_HOURLY_USD", "0"))),
        soft_cap_usd=Decimal(os.getenv("P68_KEYFRAME_SOFT_CAP_USD", "2.00")),
        hard_cap_usd=Decimal(os.getenv("P68_KEYFRAME_HARD_CAP_USD", "5.00")),
    )
    if args.command == "submit":
        result = controller.submit_missing(requests, limit=args.limit, expected_runtime_seconds=args.runtime_seconds)
    elif args.command == "refresh":
        result = controller.refresh()
    else:
        result = controller.status()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
