#!/usr/bin/env python3
"""Write a secret-free, no-spend P68 natural-motion batch plan."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal

from src.p68_motion_batch import write_motion_batch_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--output", default="p68-artifacts/motion-batch-plan.json")
    parser.add_argument("--standard-variants", type=int, default=1)
    parser.add_argument("--hero-variants", type=int, default=2)
    parser.add_argument("--runtime-seconds-per-variant", type=Decimal, default=Decimal("540"))
    args = parser.parse_args()
    result = write_motion_batch_plan(
        args.pilots_root,
        args.artifact_root,
        args.output,
        environ=os.environ,
        standard_variants=args.standard_variants,
        hero_variants=args.hero_variants,
        estimated_runtime_seconds_per_variant=args.runtime_seconds_per_variant,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
