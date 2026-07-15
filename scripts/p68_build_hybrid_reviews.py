#!/usr/bin/env python3
"""Build review-only P68 videos with deterministic science clips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.p68_hybrid_review import assemble_hybrid_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot")
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    args = parser.parse_args()
    root = Path(args.pilots_root)
    pilots = [root / args.pilot] if args.pilot else sorted(path.parent for path in root.glob("*/content-plan.json"))
    outputs = [assemble_hybrid_review(pilot, Path(args.artifact_root) / "gold" / pilot.name) for pilot in pilots]
    print(
        json.dumps(
            [
                {
                    "pilot_id": item["pilot_id"],
                    "output_path": item["render"]["output_path"],
                    "technical_pass": item["render"]["technical_pass"],
                    "preview_fallbacks": _preview_fallbacks(item["hybrid_manifest_path"]),
                    "publish_allowed": False,
                }
                for item in outputs
            ],
            indent=2,
        )
    )
    return 0


def _preview_fallbacks(path: str) -> list[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload["preview_fallback_shot_ids"]


if __name__ == "__main__":
    raise SystemExit(main())
