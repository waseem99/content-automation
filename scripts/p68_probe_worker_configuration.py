#!/usr/bin/env python3
"""Write a secret-safe P68 worker configuration presence report."""

from __future__ import annotations

import argparse
import json
import os

from src.p68_worker_configuration import write_worker_configuration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="p68-worker-configuration.json")
    args = parser.parse_args()
    result = write_worker_configuration(os.environ, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
