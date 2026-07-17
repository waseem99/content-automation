#!/usr/bin/env python3
"""Render deterministic P68 scientific animation clips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.p68_scientific_animation import ANIMATION_VERSION, render_pilot_science


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    args = parser.parse_args()
    plan = json.loads((Path(args.pilots_root) / args.pilot / "content-plan.json").read_text(encoding="utf-8"))
    output = render_pilot_science(
        plan,
        Path(args.artifact_root) / "gold" / args.pilot / "clips" / ANIMATION_VERSION.rsplit(".", 1)[-1],
    )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
