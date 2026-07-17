#!/usr/bin/env python3
"""Generate four database/bootstrap calendars and one read-only portfolio calendar."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p82_portfolio_calendar import CURRENT_BRANDS, build_portfolio_studio, expand_portfolio_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/portfolio-brands.staging.json"))
    parser.add_argument("--rawr-base", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("web/static-creator-ui/data"))
    parser.add_argument("--bootstrap-output", type=Path, default=Path(".local-production/portfolio-high-volume-bootstrap.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rawr = json.loads(args.rawr_base.read_text(encoding="utf-8"))
    portfolio = build_portfolio_studio(config, rawr)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for brand in portfolio["brands"]:
        (args.output_dir / f"{brand['brand']['slug']}-high-volume.json").write_text(json.dumps(brand, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "portfolio-high-volume.json").write_text(json.dumps(portfolio, indent=2) + "\n", encoding="utf-8")
    args.bootstrap_output.parent.mkdir(parents=True, exist_ok=True)
    args.bootstrap_output.write_text(json.dumps(expand_portfolio_config(config), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"brands": list(CURRENT_BRANDS), **portfolio["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
