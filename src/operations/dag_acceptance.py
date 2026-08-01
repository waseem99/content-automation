from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.application.campaign_dag import CampaignDagService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _timed(timings: dict[str, float], key: str, function, *args, **kwargs):
    started = time.perf_counter()
    result = function(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _key() -> str:
    return datetime.now(timezone.utc).strftime("p128-%Y%m%dt%H%M%S%fz")


def _seed_campaigns_and_graphs(
    database: Database,
    *,
    acceptance_key: str,
    campaign_count: int,
    actor: str,
) -> list[UUID]:
    with database.transaction() as conn:
        brand = conn.execute(
            "SELECT id FROM football_brief.brands WHERE active=true ORDER BY slug LIMIT 1"
        ).fetchone()
        if brand is None:
            raise RuntimeError("brand onboarding is incomplete")
        graph_ids: list[UUID] = []
        for ordinal in range(1, campaign_count + 1):
            campaign = conn.execute(
                """INSERT INTO football_brief.production_campaigns
                   (campaign_key,brand_id,name,description,status,created_by,activated_at,metadata)
                   VALUES (%s,%s,%s,%s,'active',%s,now(),%s::jsonb)
                   RETURNING id""",
                (
                    f"{acceptance_key}-c{ordinal:02d}",
                    brand["id"],
                    f"P128 DAG acceptance campaign {ordinal:02d}",
                    "Synthetic control-plane DAG acceptance; no media execution.",
                    actor,
                    _json({"p128_acceptance": True, "ordinal": ordinal}),
                ),
            ).fetchone()
            definition = {"stages": ["prepare", "complete"], "acceptance": acceptance_key}
            graph = conn.execute(
                """INSERT INTO football_brief.campaign_task_graphs
                   (campaign_id,version,graph_key,status,definition_sha256,configuration,
                    created_by,activated_by,activated_at)
                   VALUES (%s,1,%s,'active',encode(digest(%s::bytea,'sha256'),'hex'),%s::jsonb,%s,%s,now())
                   RETURNING id""",
                (
                    campaign["id"],
                    f"{acceptance_key}-g{ordinal:02d}",
                    _json(definition),
                    _json(definition),
                    actor,
                    actor,
                ),
            ).fetchone()
            graph_ids.append(UUID(str(graph["id"])))
    return graph_ids


def _insert_tasks(
    database: Database,
    *,
    graph_ids: list[UUID],
    tasks: int,
) -> None:
    per_graph = tasks // len(graph_ids)
    if per_graph * len(graph_ids) != tasks or per_graph % 2:
        raise ValueError("tasks must divide evenly across graphs and two stages")
    per_stage = per_graph // 2
    with database.transaction() as conn:
        for graph_index, graph_id in enumerate(graph_ids, start=1):
            conn.execute(
                """INSERT INTO football_brief.campaign_tasks
                   (graph_id,task_key,task_type,stage_order,required_capabilities,status,
                    priority,idempotency_key,input_fingerprint,input_payload,max_attempts)
                   SELECT %s,
                          'prepare-' || lpad(value::text,8,'0'),
                          'prepare',1,ARRAY['cpu']::text[],'queued',0,
                          'p128:' || %s::text || ':prepare:' || value::text,
                          encode(digest((%s::text || ':prepare:' || value::text)::bytea,'sha256'),'hex'),
                          jsonb_build_object('graph_index',%s,'value',value,'stage','prepare'),3
                   FROM generate_series(1,%s) value""",
                (graph_id, graph_id, graph_id, graph_index, per_stage),
            )
            conn.execute(
                """INSERT INTO football_brief.campaign_tasks
                   (graph_id,task_key,task_type,stage_order,required_capabilities,status,
                    priority,idempotency_key,input_fingerprint,input_payload,max_attempts)
                   SELECT %s,
                          'complete-' || lpad(value::text,8,'0'),
                          'complete',2,ARRAY['cpu']::text[],'blocked',0,
                          'p128:' || %s::text || ':complete:' || value::text,
                          encode(digest((%s::text || ':complete:' || value::text)::bytea,'sha256'),'hex'),
                          jsonb_build_object('graph_index',%s,'value',value,'stage','complete'),3
                   FROM generate_series(1,%s) value""",
                (graph_id, graph_id, graph_id, graph_index, per_stage),
            )
            conn.execute(
                """INSERT INTO football_brief.campaign_task_dependencies(task_id,depends_on_task_id)
                   SELECT dependent.id,prerequisite.id
                   FROM football_brief.campaign_tasks dependent
                   JOIN football_brief.campaign_tasks prerequisite
                     ON prerequisite.graph_id=dependent.graph_id
                    AND prerequisite.task_key=replace(dependent.task_key,'complete-','prepare-')
                   WHERE dependent.graph_id=%s AND dependent.task_type='complete'""",
                (graph_id,),
            )


def _register_workers(database: Database, *, workers: int, actor: str) -> list[str]:
    service = CampaignDagService(database)
    worker_ids: list[str] = []
    for ordinal in range(1, workers + 1):
        worker_id = f"dag-worker-{ordinal:03d}"
        service.register_worker(
            worker_id=worker_id,
            display_name=f"P128 Worker {ordinal:03d}",
            capabilities=["CPU", "cpu", " deterministic "],
            max_concurrency=50,
            actor=actor,
            metadata={"p128_acceptance": True, "ordinal": ordinal},
        )
        worker_ids.append(worker_id)
    return worker_ids


def _fair_claim_sample(
    database: Database,
    *,
    worker_ids: list[str],
    graph_ids: list[UUID],
) -> tuple[int, list[dict[str, Any]]]:
    service = CampaignDagService(database)
    claimed: list[dict[str, Any]] = []
    for worker_id in worker_ids:
        claimed.extend(service.claim(worker_id=worker_id, limit=10, lease_seconds=300))
    counts = {str(graph_id): 0 for graph_id in graph_ids}
    for task in claimed:
        counts[str(task["graph_id"])] += 1
    spread = max(counts.values()) - min(counts.values())
    if len(claimed) != len(worker_ids) * 10:
        raise RuntimeError(f"expected {len(worker_ids) * 10} fair claims, got {len(claimed)}")
    if spread > 1:
        raise RuntimeError(f"campaign fairness spread exceeded one: {counts}")
    return spread, claimed


def _pause_isolation(database: Database, *, graph_id: UUID, worker_id: str, actor: str) -> int:
    service = CampaignDagService(database)
    service.set_graph_state(graph_id=graph_id, action="pause", actor=actor)
    claimed = service.claim(worker_id=worker_id, limit=50, lease_seconds=300)
    paused_claims = sum(1 for task in claimed if str(task["graph_id"]) == str(graph_id))
    service.set_graph_state(graph_id=graph_id, action="resume", actor=actor)
    return paused_claims


def _recover_and_restart(
    database: Database,
    *,
    claimed: list[dict[str, Any]],
    actor: str,
) -> int:
    stale = claimed[:100]
    stale_ids = [int(task["id"]) for task in stale]
    with database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.campaign_task_attempts
               SET lease_expires_at=now()-interval '1 minute'
               WHERE id=ANY(%s::bigint[])""",
            ([int(task["attempt"]["id"]) for task in stale],),
        )
        conn.execute(
            """UPDATE football_brief.campaign_tasks
               SET lease_expires_at=now()-interval '1 minute'
               WHERE id=ANY(%s::bigint[])""",
            (stale_ids,),
        )
    recovered = CampaignDagService(database).recover_stale_leases(actor=actor, limit=1000)
    if recovered["recovered"] != len(stale):
        raise RuntimeError(f"expected {len(stale)} recovered leases, got {recovered}")
    restarted_service = CampaignDagService(database)
    reclaimed: list[dict[str, Any]] = []
    for ordinal in range(1, 11):
        reclaimed.extend(
            restarted_service.claim(
                worker_id=f"dag-worker-{ordinal:03d}",
                limit=10,
                lease_seconds=300,
            )
        )
    reclaimed_ids = {int(task["id"]) for task in reclaimed}
    if not set(stale_ids).issubset(reclaimed_ids):
        raise RuntimeError("restarted workers did not reclaim every expired lease")
    return int(recovered["recovered"])


def _reset_running_for_bulk_terminalization(database: Database) -> None:
    with database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.campaign_task_attempts
               SET status='abandoned',error_code='acceptance_bulk_transition',finished_at=now()
               WHERE status='running'"""
        )
        conn.execute(
            """UPDATE football_brief.campaign_tasks
               SET status='queued',available_at=now(),current_attempt_id=NULL,
                   current_worker_id=NULL,current_lease_token=NULL,
                   heartbeat_at=NULL,lease_expires_at=NULL
               WHERE status='running'"""
        )


def _terminalize_stage(database: Database, *, stage_order: int) -> int:
    with database.transaction() as conn:
        inserted = conn.execute(
            """INSERT INTO football_brief.campaign_task_attempts
               (task_id,attempt_number,worker_id,status,input_fingerprint,
                output_fingerprint,terminal_fingerprint,output_payload,
                lease_expires_at,finished_at)
               SELECT task.id,task.attempt_count+1,
                      'dag-worker-' || lpad((((task.id-1) %% 100)+1)::text,3,'0'),
                      'succeeded',task.input_fingerprint,
                      encode(digest((task.id::text || ':output')::bytea,'sha256'),'hex'),
                      encode(digest((task.id::text || ':terminal')::bytea,'sha256'),'hex'),
                      jsonb_build_object('synthetic',true,'task_id',task.id),
                      now(),now()
               FROM football_brief.campaign_tasks task
               JOIN football_brief.campaign_task_graphs graph ON graph.id=task.graph_id
               WHERE task.stage_order=%s AND task.status='queued' AND graph.status='active'
               RETURNING id,task_id""",
            (stage_order,),
        ).fetchall()
        conn.execute(
            """UPDATE football_brief.campaign_tasks task
               SET status='succeeded',attempt_count=attempt.attempt_number,
                   output_fingerprint=attempt.output_fingerprint,
                   output_payload=attempt.output_payload,
                   terminal_fingerprint=attempt.terminal_fingerprint,
                   finished_at=attempt.finished_at,
                   current_attempt_id=NULL,current_worker_id=NULL,current_lease_token=NULL,
                   heartbeat_at=NULL,lease_expires_at=NULL
               FROM football_brief.campaign_task_attempts attempt
               WHERE attempt.task_id=task.id AND attempt.id=ANY(%s::bigint[])""",
            ([int(row["id"]) for row in inserted],),
        )
        if stage_order == 1:
            conn.execute(
                """UPDATE football_brief.campaign_tasks dependent
                   SET status='queued',available_at=now()
                   WHERE dependent.stage_order=2 AND dependent.status='blocked'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM football_brief.campaign_task_dependencies link
                         JOIN football_brief.campaign_tasks prerequisite
                           ON prerequisite.id=link.depends_on_task_id
                         WHERE link.task_id=dependent.id AND prerequisite.status<>'succeeded'
                     )"""
            )
        return len(inserted)


def run_acceptance(
    *,
    tasks: int = 1_000_000,
    workers: int = 100,
    campaigns: int = 10,
    acceptance_key: str | None = None,
    actor: str = "local-admin",
) -> dict[str, Any]:
    if not 1_000 <= tasks <= 5_000_000:
        raise ValueError("tasks must be between 1,000 and 5,000,000")
    if not 1 <= workers <= 500:
        raise ValueError("workers must be between 1 and 500")
    if not 2 <= campaigns <= 100:
        raise ValueError("campaigns must be between 2 and 100")
    key = acceptance_key or _key()
    timings: dict[str, float] = {}
    database = Database(get_database_settings())
    database.open(require_schema=True)
    acceptance_id: UUID | None = None
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            if operator is None:
                raise RuntimeError("operator onboarding is incomplete")
            acceptance = conn.execute(
                """INSERT INTO football_brief.dag_acceptance_runs
                   (acceptance_key,status,requested_tasks,requested_workers,campaign_count,
                    requested_by,environment)
                   VALUES (%s,'running',%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                (
                    key,
                    tasks,
                    workers,
                    campaigns,
                    actor,
                    _json({
                        "hostname": socket.gethostname(),
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                        "git_sha": os.getenv("GITHUB_SHA") or os.getenv("OPS_GIT_SHA"),
                        "synthetic_media": True,
                        "paid_execution": False,
                        "publishing": False,
                    }),
                ),
            ).fetchone()
            acceptance_id = UUID(str(acceptance["id"]))

        graph_ids = _timed(
            timings,
            "seed_campaigns_and_graphs",
            _seed_campaigns_and_graphs,
            database,
            acceptance_key=key,
            campaign_count=campaigns,
            actor=actor,
        )
        worker_ids = _timed(
            timings,
            "register_workers",
            _register_workers,
            database,
            workers=workers,
            actor=actor,
        )
        _timed(timings, "insert_tasks", _insert_tasks, database, graph_ids=graph_ids, tasks=tasks)
        spread, claimed = _timed(
            timings,
            "fair_claim_sample",
            _fair_claim_sample,
            database,
            worker_ids=worker_ids,
            graph_ids=graph_ids,
        )
        paused_claims = _timed(
            timings,
            "pause_isolation",
            _pause_isolation,
            database,
            graph_id=graph_ids[0],
            worker_id=worker_ids[0],
            actor=actor,
        )
        recovered = _timed(
            timings,
            "recover_and_restart",
            _recover_and_restart,
            database,
            claimed=claimed,
            actor=actor,
        )
        _timed(timings, "reset_running", _reset_running_for_bulk_terminalization, database)
        stage_one = _timed(timings, "terminalize_stage_one", _terminalize_stage, database, stage_order=1)
        stage_two = _timed(timings, "terminalize_stage_two", _terminalize_stage, database, stage_order=2)

        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.campaign_task_graphs graph
                   SET status='completed',completed_at=now()
                   WHERE graph.id=ANY(%s::uuid[])
                     AND NOT EXISTS (
                         SELECT 1 FROM football_brief.campaign_tasks task
                         WHERE task.graph_id=graph.id AND task.status<>'succeeded'
                     )""",
                (graph_ids,),
            )
            counters = dict(
                conn.execute(
                    """SELECT
                           count(*)::bigint AS total_tasks,
                           count(*) FILTER (WHERE status='succeeded')::bigint AS succeeded_tasks,
                           count(*) FILTER (WHERE status IN ('succeeded','failed','cancelled','dead_letter'))::bigint AS terminal_tasks
                       FROM football_brief.campaign_tasks WHERE graph_id=ANY(%s::uuid[])""",
                    (graph_ids,),
                ).fetchone()
            )
            duplicate_terminal = int(
                conn.execute(
                    """SELECT count(*)::bigint AS value FROM (
                           SELECT task_id
                           FROM football_brief.campaign_task_attempts
                           WHERE status='succeeded'
                           GROUP BY task_id HAVING count(*)>1
                       ) duplicate"""
                ).fetchone()["value"]
            )
            passed = (
                int(counters["total_tasks"]) == tasks
                and int(counters["terminal_tasks"]) == tasks
                and int(counters["succeeded_tasks"]) == tasks
                and duplicate_terminal == 0
                and recovered > 0
                and spread <= 1
                and paused_claims == 0
                and stage_one + stage_two <= tasks
            )
            conn.execute(
                """UPDATE football_brief.dag_acceptance_runs
                   SET status=%s,terminal_tasks=%s,succeeded_tasks=%s,
                       duplicate_terminal_attempts=%s,recovered_leases=%s,
                       fairness_spread=%s,paused_claims=%s,cancelled_tasks=0,
                       timings_ms=%s::jsonb,counters=%s::jsonb,
                       completed_at=now(),error=%s::jsonb
                   WHERE id=%s""",
                (
                    "passed" if passed else "failed",
                    counters["terminal_tasks"],
                    counters["succeeded_tasks"],
                    duplicate_terminal,
                    recovered,
                    spread,
                    paused_claims,
                    _json(timings),
                    _json({**counters, "stage_one_inserted": stage_one, "stage_two_inserted": stage_two}),
                    _json({}) if passed else _json({"reason": "acceptance_mismatch"}),
                    acceptance_id,
                ),
            )
        if not passed:
            raise RuntimeError(
                f"DAG acceptance failed: counters={counters}, duplicate={duplicate_terminal}, "
                f"recovered={recovered}, spread={spread}, paused={paused_claims}"
            )
        return {
            "ok": True,
            "kind": "p128_dag_acceptance",
            "acceptance_key": key,
            "tasks": tasks,
            "workers": workers,
            "campaigns": campaigns,
            "recovered_leases": recovered,
            "fairness_spread": spread,
            "timings_ms": timings,
        }
    except Exception as exc:
        if acceptance_id is not None:
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.dag_acceptance_runs
                       SET status='failed',error=%s::jsonb,timings_ms=%s::jsonb,completed_at=now()
                       WHERE id=%s AND status='running'""",
                    (_json({"type": type(exc).__name__, "message": str(exc)}), _json(timings), acceptance_id),
                )
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P128 million-task DAG acceptance")
    parser.add_argument("--tasks", type=int, default=1_000_000)
    parser.add_argument("--workers", type=int, default=100)
    parser.add_argument("--campaigns", type=int, default=10)
    parser.add_argument("--acceptance-key")
    args = parser.parse_args()
    print(_json(run_acceptance(
        tasks=args.tasks,
        workers=args.workers,
        campaigns=args.campaigns,
        acceptance_key=args.acceptance_key,
    )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
