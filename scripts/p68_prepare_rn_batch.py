#!/usr/bin/env python3
"""Create a non-secret, offline readiness report for P68 RN generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.p68_batch_preflight import write_batch_preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--output", default="p68-artifacts/rn-generation-preflight.json")
    args = parser.parse_args()
    result = write_batch_preflight(
        Path(args.pilots_root),
        Path(args.artifact_root),
        Path(args.output),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
