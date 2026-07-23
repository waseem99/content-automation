from __future__ import annotations

import argparse
import json
import time

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.always_on_pipeline import AlwaysOnLocalPipelineService
from src.operations.local_worker_v2 import (
    ALL_SUPPORTED_TYPES,
    AlwaysOnLocalGenerationWorker,
    _parse_types,
)


class PinnedLineageLocalGenerationWorker(AlwaysOnLocalGenerationWorker):
    """P104 worker using the workflow/profile/script-pinned queue service."""

    def __init__(self, database: Database, *, allowed_job_types=ALL_SUPPORTED_TYPES) -> None:
        super().__init__(database, allowed_job_types=allowed_job_types)
        self.pipeline = AlwaysOnLocalPipelineService(database)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the pinned-lineage always-on local worker.")
    parser.add_argument("--once", action="store_true", help="Reconcile or claim at most one job.")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument(
        "--job-types",
        type=_parse_types,
        default=frozenset(ALL_SUPPORTED_TYPES),
        help="Comma-separated subset of script,narration,keyframe,preview.",
    )
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = PinnedLineageLocalGenerationWorker(database, allowed_job_types=args.job_types)
    try:
        while True:
            result = worker.run_once()
            print(json.dumps(result, default=str, sort_keys=True), flush=True)
            if args.once:
                return 0 if result.get("ok") else 1
            if not result.get("claimed") and not result.get("reconciled"):
                time.sleep(max(args.poll_seconds, 0.5))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
