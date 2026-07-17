#!/usr/bin/env python3
"""Write a no-spend, provider-free P68 six-pilot completion audit."""

from __future__ import annotations

import argparse
import json
import os

from src.p68_completion_audit import write_completion_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--output", default="p68-artifacts/p68-completion-audit.json")
    args = parser.parse_args()

    result = write_completion_audit(
        args.pilots_root,
        args.artifact_root,
        args.output,
        environ=os.environ,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["roster_complete"] and result["specs_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
