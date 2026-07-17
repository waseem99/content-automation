#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p80_brand_month_studio import build_brand_month_studio


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", default="rawr-nation")
    parser.add_argument("--config", type=Path, default=Path("config/portfolio-brands.staging.json"))
    parser.add_argument("--output", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    args = parser.parse_args()
    result = build_brand_month_studio(json.loads(args.config.read_text(encoding="utf-8")), brand_slug=args.brand)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
