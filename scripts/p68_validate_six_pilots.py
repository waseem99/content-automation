#!/usr/bin/env python3
"""Validate the six P68 production packs without generating or approving media."""

from __future__ import annotations

import argparse
import json

from src.p68_pilot_batch import write_spec_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--output", default="p68-artifacts/six-pilot-spec-readiness.json")
    args = parser.parse_args()
    result = write_spec_readiness(args.pilots_root, args.output)
    print(json.dumps(result, indent=2))
    return 0 if result["all_specs_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
