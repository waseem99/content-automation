from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.always_on_pipeline import AlwaysOnLocalPipelineService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Continue explicitly approved local work in bounded batches.")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    database = Database(get_database_settings())
    database.open(require_schema=True)
    service = AlwaysOnLocalPipelineService(database)
    actor = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer")
    runtime_root = Path(os.getenv("LOCAL_RUNTIME_ROOT", ".runtime"))
    heartbeat = runtime_root / "continuation-heartbeat.json"
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            try:
                result = service.continue_approved(
                    limit=args.limit,
                    actor=actor,
                    include_audio=True,
                    include_visuals=True,
                    include_previews=True,
                )
                payload = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ok": True,
                    "result": result,
                    "automatic_approval": False,
                    "live_publishing": False,
                }
            except Exception as exc:
                payload = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "automatic_approval": False,
                    "live_publishing": False,
                }
            heartbeat.write_text(json.dumps(payload, default=str, sort_keys=True), encoding="utf-8")
            print(json.dumps(payload, default=str, sort_keys=True), flush=True)
            if args.once:
                return 0 if payload["ok"] else 1
            time.sleep(max(10.0, args.interval_seconds))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
