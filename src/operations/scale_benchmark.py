from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from datetime import date, datetime, timezone
from typing import Any, Iterable, TypeVar
from uuid import UUID

from src.application.campaigns.models import (
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.pre_generation.validated_service import ValidatedPreGenerationService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


T = TypeVar("T")
MAX_ITEMS_PER_REQUEST = 10_000
CHECK_INSERT_RUN_BATCH = 250


def _utc_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S%fz")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _timed(timings: dict[str, float], key: str, function, *args, **kwargs):
    started = time.perf_counter()
    result = function(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _chunks(values: list[T], size: int = MAX_ITEMS_PER_REQUEST) -> Iterable[list[T]]:
    if size < 1:
        raise ValueError("chunk size must be positive")
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _items(count: int, *, platform_name: str) -> list[CampaignItemInput]:
    scheduled = date.today()
    return [
        CampaignItemInput(
            item_key=f"scale-{ordinal:05d}",
            title=f"Scale benchmark item {ordinal:05d}",
            topic=f"Unique database-native benchmark brief {ordinal:05d} for measured campaign-control validation.",
            objective="Measure campaign ingestion, validation, activation and durable orchestration retention.",
            audience="Internal benchmark only",
            format_name="master_video",
            primary_platform=platform_name,
            target_platforms=[platform_name],
            target_duration_seconds=45,
            short_cut_count=2,
            language="en-US",
            scheduled_for=scheduled,
            priority=50,
            metadata={"synthetic_benchmark": True, "ordinal": ordinal},
        )
        for ordinal in range(1, count + 1)
    ]


def _add_item_chunks(
    service: ValidatedCampaignService,
    *,
    campaign_version_id: UUID,
    items: list[CampaignItemInput],
    actor: str,
) -> dict[str, Any]:
    changed = 0
    submitted = 0
    counts: dict[str, int] = {
        "item_count": 0,
        "valid_item_count": 0,
        "invalid_item_count": 0,
    }
    chunk_count = 0
    for chunk in _chunks(items):
        result = service.add_items(
            campaign_version_id=campaign_version_id,
            request=CampaignItemsAddRequest(items=chunk),
            actor=actor,
        )
        chunk_count += 1
        submitted += int(result["submitted"])
        changed += int(result["changed"])
        counts = dict(result["counts"])
    return {
        "submitted": submitted,
        "changed": changed,
        "counts": counts,
        "chunks": chunk_count,
    }


def _campaign_run_ids(database: Database, *, campaign_version_id: UUID) -> list[UUID]:
    """Return the campaign's durable runs in stable order for bounded retention batches."""

    with database.connection() as conn:
        rows = conn.execute(
            """SELECT run.id
               FROM football_brief.pre_generation_runs run
               JOIN football_brief.production_campaign_items item
                 ON item.id=run.campaign_item_id
               WHERE item.campaign_version_id=%s
               ORDER BY run.id""",
            (campaign_version_id,),
        ).fetchall()
    return [UUID(str(row["id"])) for row in rows]


def _insert_retained_checks_in_batches(
    database: Database,
    *,
    run_ids: list[UUID],
    checks_per_run: int,
    run_batch_size: int = CHECK_INSERT_RUN_BATCH,
) -> dict[str, int]:
    """Insert deterministic synthetic checks in bounded, independently committed batches.

    PostgreSQL validates the foreign key for every retained check. A single
    million-row statement can legitimately exceed the production statement
    timeout even though the control plane is healthy. Batching by stable run IDs
    preserves the exact dataset and idempotency contract while bounding lock and
    statement duration.
    """

    if run_batch_size < 1:
        raise ValueError("check insert run batch size must be positive")
    if checks_per_run < 1:
        return {"inserted": 0, "batches": 0, "run_batch_size": run_batch_size}

    inserted_total = 0
    batch_count = 0
    for run_batch in _chunks(run_ids, run_batch_size):
        with database.transaction() as conn:
            inserted_total += int(
                conn.execute(
                    """WITH selected AS (
                           SELECT unnest(%s::uuid[]) AS id
                       ), inserted AS (
                           INSERT INTO football_brief.pre_generation_checks
                           (run_id,stage,check_key,rule_version,status,score,evidence)
                           SELECT selected.id,'scale_benchmark',
                                  'retention-' || series.value::text,
                                  'p125-retention-v1','passed',100,
                                  jsonb_build_object('synthetic',true,'ordinal',series.value)
                           FROM selected
                           CROSS JOIN generate_series(1,%s) AS series(value)
                           ON CONFLICT (run_id,stage,check_key,rule_version) DO NOTHING
                           RETURNING 1
                       ) SELECT count(*)::bigint AS value FROM inserted""",
                    (run_batch, checks_per_run),
                ).fetchone()["value"]
            )
        batch_count += 1
    return {
        "inserted": inserted_total,
        "batches": batch_count,
        "run_batch_size": run_batch_size,
    }


def run_benchmark(
    *,
    items: int,
    checks_per_run: int,
    claim_sample: int,
    actor: str,
    benchmark_key: str | None = None,
) -> dict[str, Any]:
    if not 1 <= items <= 20000:
        raise ValueError("items must be between 1 and 20000")
    if not 0 <= checks_per_run <= 250:
        raise ValueError("checks_per_run must be between 0 and 250")
    if not 0 <= claim_sample <= 500:
        raise ValueError("claim_sample must be between 0 and 500")
    requested_checks = items * checks_per_run
    if requested_checks > 5_000_000:
        raise ValueError("requested synthetic checks cannot exceed 5,000,000")

    key = benchmark_key or f"p125-{items}-{requested_checks}-{_utc_key()}"
    timings: dict[str, float] = {}
    database = Database(get_database_settings())
    database.open(require_schema=True)
    benchmark_id: UUID | None = None
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            if operator is None:
                raise RuntimeError(f"benchmark operator is missing or inactive: {actor}")
            brand = conn.execute(
                "SELECT id,primary_platform FROM football_brief.brands WHERE active=true ORDER BY slug LIMIT 1"
            ).fetchone()
            if brand is None:
                raise RuntimeError("no active benchmark brand exists")
            run = conn.execute(
                """INSERT INTO football_brief.scale_benchmark_runs
                   (benchmark_key,status,requested_items,requested_checks,claim_sample,
                    requested_by,environment)
                   VALUES (%s,'running',%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                (
                    key,
                    items,
                    requested_checks,
                    min(claim_sample, items),
                    actor,
                    _json(
                        {
                            "hostname": socket.gethostname(),
                            "platform": platform.platform(),
                            "python": platform.python_version(),
                            "git_sha": os.getenv("GITHUB_SHA") or os.getenv("OPS_GIT_SHA"),
                            "control_plane_only": True,
                            "final_video_generation_measured": False,
                            "maximum_items_per_request": MAX_ITEMS_PER_REQUEST,
                            "check_insert_run_batch": CHECK_INSERT_RUN_BATCH,
                        }
                    ),
                ),
            ).fetchone()
            benchmark_id = UUID(str(run["id"]))

        campaign_service = ValidatedCampaignService(database)
        item_payload = _timed(
            timings,
            "build_items",
            _items,
            items,
            platform_name=str(brand["primary_platform"]),
        )
        created = _timed(
            timings,
            "create_campaign",
            campaign_service.create_campaign,
            CampaignCreateRequest(
                campaign_key=key,
                brand_id=UUID(str(brand["id"])),
                name=f"P125 Scale Benchmark {items:,}",
                description="Synthetic database control-plane benchmark; no rendering or publishing.",
                metadata={"synthetic_benchmark": True},
            ),
            actor=actor,
        )
        campaign_id = UUID(str(created["campaign"]["id"]))
        version_id = UUID(str(created["versions"][0]["id"]))
        first_add = _timed(
            timings,
            "insert_items",
            _add_item_chunks,
            campaign_service,
            campaign_version_id=version_id,
            items=item_payload,
            actor=actor,
        )
        second_add = _timed(
            timings,
            "idempotent_item_replay",
            _add_item_chunks,
            campaign_service,
            campaign_version_id=version_id,
            items=item_payload,
            actor=actor,
        )
        validation = _timed(
            timings,
            "validate_items",
            campaign_service.validate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        if not validation["ok"]:
            raise RuntimeError(f"scale campaign validation failed: {validation}")
        activation = _timed(
            timings,
            "activate_campaign",
            campaign_service.activate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        pre = ValidatedPreGenerationService(database)
        ensured = _timed(
            timings,
            "ensure_runs",
            pre.ensure_runs,
            campaign_id=campaign_id,
            actor=actor,
        )
        run_ids = _timed(
            timings,
            "load_run_ids",
            _campaign_run_ids,
            database,
            campaign_version_id=version_id,
        )
        if len(run_ids) != items:
            raise RuntimeError(
                f"expected {items} durable runs before retention benchmark, found {len(run_ids)}"
            )

        inserted_checks = 0
        duplicate_check_inserts = 0
        check_insert_batches = 0
        check_replay_batches = 0
        if checks_per_run:
            inserted = _timed(
                timings,
                "insert_checks",
                _insert_retained_checks_in_batches,
                database,
                run_ids=run_ids,
                checks_per_run=checks_per_run,
            )
            inserted_checks = int(inserted["inserted"])
            check_insert_batches = int(inserted["batches"])
            replayed = _timed(
                timings,
                "idempotent_check_replay",
                _insert_retained_checks_in_batches,
                database,
                run_ids=run_ids,
                checks_per_run=checks_per_run,
            )
            duplicate_check_inserts = int(replayed["inserted"])
            check_replay_batches = int(replayed["batches"])

        claimed: list[dict[str, Any]] = []
        if claim_sample:
            claimed = _timed(
                timings,
                "claim_sample",
                pre.claim,
                owner=f"benchmark-{key}",
                limit=min(claim_sample, items),
                lease_seconds=300,
            )
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.pre_generation_runs
                       SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                           next_attempt_at=now(),updated_at=now()
                       WHERE id=ANY(%s::uuid[])""",
                    ([row["id"] for row in claimed],),
                )

        with database.connection() as conn:
            counters = dict(
                conn.execute(
                    """SELECT
                           (SELECT count(*) FROM football_brief.production_campaign_items
                            WHERE campaign_version_id=%s)::int AS items,
                           (SELECT count(*) FROM football_brief.pre_generation_runs run
                            JOIN football_brief.production_campaign_items item
                              ON item.id=run.campaign_item_id
                            WHERE item.campaign_version_id=%s)::int AS runs,
                           (SELECT count(*) FROM football_brief.pre_generation_checks check_row
                            JOIN football_brief.pre_generation_runs run ON run.id=check_row.run_id
                            JOIN football_brief.production_campaign_items item
                              ON item.id=run.campaign_item_id
                            WHERE item.campaign_version_id=%s
                              AND check_row.stage='scale_benchmark')::bigint AS checks""",
                    (version_id, version_id, version_id),
                ).fetchone()
            )
        duplicate_item_rows = max(0, int(counters["items"]) - items)
        passed = (
            counters["items"] == items
            and counters["runs"] == items
            and counters["checks"] == requested_checks
            and inserted_checks == requested_checks
            and duplicate_item_rows == 0
            and duplicate_check_inserts == 0
            and len(claimed) == min(claim_sample, items)
            and validation["counts"]["invalid_item_count"] == 0
        )
        result = {
            "benchmark_key": key,
            "benchmark_id": str(benchmark_id),
            "campaign_id": str(campaign_id),
            "status": "passed" if passed else "failed",
            "requested": {"items": items, "checks": requested_checks},
            "inserted": {
                "items": first_add["counts"]["item_count"],
                "runs": counters["runs"],
                "checks": inserted_checks,
                "item_chunks": first_add["chunks"],
                "check_batches": check_insert_batches,
                "check_run_batch_size": CHECK_INSERT_RUN_BATCH,
            },
            "idempotency": {
                "items_after_replay": second_add["counts"]["item_count"],
                "replay_chunks": second_add["chunks"],
                "check_replay_batches": check_replay_batches,
                "duplicate_item_rows": duplicate_item_rows,
                "duplicate_check_rows": duplicate_check_inserts,
            },
            "claim_sample": len(claimed),
            "timings_ms": timings,
            "counters": counters,
            "control_plane_only": True,
            "final_video_generation_measured": False,
            "activation": {
                "activated_items": activation["activated_items"],
                "created_runs": ensured["created"],
            },
        }
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.scale_benchmark_runs
                   SET status=%s,campaign_id=%s,inserted_items=%s,inserted_runs=%s,
                       inserted_checks=%s,duplicate_items=%s,duplicate_checks=%s,
                       timings_ms=%s::jsonb,counters=%s::jsonb,completed_at=now()
                   WHERE id=%s""",
                (
                    result["status"],
                    campaign_id,
                    result["inserted"]["items"],
                    result["inserted"]["runs"],
                    result["inserted"]["checks"],
                    result["idempotency"]["duplicate_item_rows"],
                    result["idempotency"]["duplicate_check_rows"],
                    _json(timings),
                    _json(
                        {
                            **counters,
                            "check_batches": check_insert_batches,
                            "check_replay_batches": check_replay_batches,
                            "check_run_batch_size": CHECK_INSERT_RUN_BATCH,
                        }
                    ),
                    benchmark_id,
                ),
            )
        if not passed:
            raise RuntimeError(_json(result))
        return result
    except Exception as exc:
        if benchmark_id is not None:
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.scale_benchmark_runs
                       SET status='failed',error=%s::jsonb,completed_at=now() WHERE id=%s""",
                    (_json({"type": type(exc).__name__, "message": str(exc)[:4000]}), benchmark_id),
                )
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure database-native campaign and orchestration retention without rendering video."
    )
    parser.add_argument("--items", type=int, default=10_000)
    parser.add_argument("--checks-per-run", type=int, default=100)
    parser.add_argument("--claim-sample", type=int, default=500)
    parser.add_argument("--actor", default="local-admin")
    parser.add_argument("--benchmark-key")
    args = parser.parse_args()
    result = run_benchmark(
        items=args.items,
        checks_per_run=args.checks_per_run,
        claim_sample=args.claim_sample,
        actor=args.actor,
        benchmark_key=args.benchmark_key,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
