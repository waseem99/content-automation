#!/usr/bin/env python3
"""Materialize the four-brand month factory for local and static-UI review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p79_month_factory import build_month_factory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/portfolio-brands.staging.json"))
    parser.add_argument("--pilots-root", type=Path, default=Path("p68-pilots"))
    parser.add_argument("--artifacts-root", type=Path, default=Path("p68-artifacts"))
    parser.add_argument("--output", type=Path, default=Path("web/static-creator-ui/data/month-factory.json"))
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = build_month_factory(config, pilots_root=args.pilots_root, artifacts_root=args.artifacts_root, batch_size=args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), **result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
