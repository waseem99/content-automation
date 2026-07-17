#!/usr/bin/env python3
"""Select generated clip variants for a review assembly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.p68_candidate_selection import select_candidates


def _selections(value: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in value.split(","):
        try:
            shot_id, variant = item.strip().split("=", 1)
            result[shot_id] = int(variant)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError("use SHOT=VARIANT pairs, for example S01=2,S02=1") from exc
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--select", required=True, type=_selections, dest="selections")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    args = parser.parse_args()
    generated = Path(args.artifact_root) / "gold" / args.pilot / "clips" / "generated"
    result = select_candidates(
        generated / "candidate-manifest.json",
        args.selections,
        reviewer=args.reviewer,
        note=args.note,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
