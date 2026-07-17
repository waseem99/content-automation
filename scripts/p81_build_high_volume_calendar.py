#!/usr/bin/env python3
"""Build the 120-master Rawr Nation calendar and bootstrap config."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p81_high_volume_calendar import build_high_volume_studio, expand_rawr_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/portfolio-brands.staging.json"))
    parser.add_argument("--base-studio", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    parser.add_argument("--output", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-high-volume.json"))
    parser.add_argument("--bootstrap-output", type=Path, default=Path(".local-production/rawr-high-volume-bootstrap.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    base = json.loads(args.base_studio.read_text(encoding="utf-8"))
    studio = build_high_volume_studio(base, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(studio, indent=2) + "\n", encoding="utf-8")
    args.bootstrap_output.parent.mkdir(parents=True, exist_ok=True)
    args.bootstrap_output.write_text(json.dumps(expand_rawr_config(config), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(studio["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
