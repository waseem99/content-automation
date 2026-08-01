from __future__ import annotations

import argparse
import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from uuid import UUID

from src.application.pre_generation.service import PreGenerationError, PreGenerationService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _log(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, **fields}, sort_keys=True, default=str), flush=True)


def _process_one(
    database: Database,
    *,
    row: dict[str, Any],
    actor: str,
    max_steps: int,
) -> dict[str, Any]:
    service = PreGenerationService(database)
    return service.process_claim(
        run_id=UUID(str(row["id"])),
        lease_token=UUID(str(row["lease_token"])),
        actor=actor,
        max_steps=max_steps,
    )


def run_worker(
    *,
    once: bool,
    poll_seconds: float,
    batch_size: int,
    concurrency: int,
    lease_seconds: int,
    max_steps: int,
) -> int:
    if not _truthy(os.getenv("PRE_GENERATION_AUTOPILOT_ENABLED", "true")):
        _log("pre_generation_worker_disabled")
        return 0
    actor = os.getenv("PRE_GENERATION_WORKER_OPERATOR_ID", "local-reviewer").strip()
    worker_id = os.getenv("PRE_GENERATION_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}").strip()
    database = Database(get_database_settings())
    database.open(require_schema=True)
    service = PreGenerationService(database)
    _log(
        "pre_generation_worker_started",
        worker_id=worker_id,
        actor=actor,
        batch_size=batch_size,
        concurrency=concurrency,
        lease_seconds=lease_seconds,
        max_steps=max_steps,
    )
    try:
        while True:
            try:
                ensured = service.ensure_runs(actor=actor)
                claimed = service.claim(
                    owner=worker_id,
                    limit=batch_size,
                    lease_seconds=lease_seconds,
                )
                if not claimed:
                    if once:
                        _log("pre_generation_worker_idle", ensured=ensured)
                        return 0
                    time.sleep(poll_seconds)
                    continue
                _log("pre_generation_batch_claimed", count=len(claimed), ensured=ensured)
                completed = 0
                terminal = 0
                waiting = 0
                failed = 0
                with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="pre-generation") as pool:
                    futures = {
                        pool.submit(
                            _process_one,
                            database,
                            row=row,
                            actor=actor,
                            max_steps=max_steps,
                        ): row
                        for row in claimed
                    }
                    for future in as_completed(futures):
                        row = futures[future]
                        try:
                            result = future.result()
                            completed += 1
                            terminal += int(bool(result.get("terminal")))
                            waiting += int(bool(result.get("waiting")))
                            _log(
                                "pre_generation_item_processed",
                                run_id=str(row["id"]),
                                result=result,
                            )
                        except PreGenerationError as exc:
                            failed += 1
                            _log(
                                "pre_generation_item_error",
                                run_id=str(row["id"]),
                                code=exc.code,
                                details=exc.details,
                            )
                        except Exception as exc:  # worker remains alive; lease recovery handles interrupted items
                            failed += 1
                            _log(
                                "pre_generation_item_crashed",
                                run_id=str(row["id"]),
                                error_type=type(exc).__name__,
                                error=str(exc)[:1000],
                            )
                _log(
                    "pre_generation_batch_completed",
                    claimed=len(claimed),
                    completed=completed,
                    terminal=terminal,
                    waiting=waiting,
                    failed=failed,
                )
                if once:
                    return 1 if failed else 0
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                _log(
                    "pre_generation_worker_loop_error",
                    error_type=type(exc).__name__,
                    error=str(exc)[:1000],
                )
                if once:
                    return 1
                time.sleep(max(poll_seconds, 3.0))
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Database-native pre-generation autopilot worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("PRE_GENERATION_POLL_SECONDS", "3")),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("PRE_GENERATION_BATCH_SIZE", "25")),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("PRE_GENERATION_CONCURRENCY", "4")),
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("PRE_GENERATION_LEASE_SECONDS", "600")),
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=int(os.getenv("PRE_GENERATION_MAX_STEPS", "12")),
    )
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size must be between 1 and 500")
    if not 1 <= args.concurrency <= 64:
        parser.error("--concurrency must be between 1 and 64")
    if not 30 <= args.lease_seconds <= 3600:
        parser.error("--lease-seconds must be between 30 and 3600")
    if not 1 <= args.max_steps <= 20:
        parser.error("--max-steps must be between 1 and 20")
    return run_worker(
        once=args.once,
        poll_seconds=max(args.poll_seconds, 0.2),
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        lease_seconds=args.lease_seconds,
        max_steps=args.max_steps,
    )


if __name__ == "__main__":
    raise SystemExit(main())
