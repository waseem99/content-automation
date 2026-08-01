from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.campaign_dag import CampaignDagService
from src.infrastructure.database.connection import Database
from src.operations import dag_acceptance as acceptance


def _recover_and_restart(
    database: Database,
    *,
    claimed: list[dict[str, Any]],
    actor: str,
) -> int:
    stale = claimed[:100]
    stale_ids = [int(task["id"]) for task in stale]
    stale_attempt_ids = [int(task["attempt"]["id"]) for task in stale]
    with database.transaction() as conn:
        conn.execute(
            """UPDATE football_brief.campaign_task_attempts
               SET status='abandoned',error_code='acceptance_restart_reset',finished_at=now()
               WHERE status='running' AND NOT (id=ANY(%s::bigint[]))""",
            (stale_attempt_ids,),
        )
        conn.execute(
            """UPDATE football_brief.campaign_tasks
               SET status='queued',available_at=now(),current_attempt_id=NULL,
                   current_worker_id=NULL,current_lease_token=NULL,
                   heartbeat_at=NULL,lease_expires_at=NULL
               WHERE status='running' AND NOT (id=ANY(%s::bigint[]))""",
            (stale_ids,),
        )
        conn.execute(
            """UPDATE football_brief.campaign_task_attempts
               SET lease_expires_at=now()-interval '1 minute'
               WHERE id=ANY(%s::bigint[])""",
            (stale_attempt_ids,),
        )
        conn.execute(
            """UPDATE football_brief.campaign_tasks
               SET lease_expires_at=now()-interval '1 minute',priority=1000
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
    if set(stale_ids) != reclaimed_ids:
        raise RuntimeError(
            f"restarted workers did not reclaim the exact expired set: "
            f"expected={len(stale_ids)} actual={len(reclaimed_ids)}"
        )
    return int(recovered["recovered"])


def _terminalize_stage(database: Database, *, stage_order: int) -> int:
    total = 0
    with database.connection() as conn:
        graph_ids = [
            UUID(str(row["id"]))
            for row in conn.execute(
                "SELECT id FROM football_brief.campaign_task_graphs WHERE status='active' ORDER BY id"
            ).fetchall()
        ]
    for graph_id in graph_ids:
        with database.transaction() as conn:
            cursor = conn.execute(
                """WITH inserted AS (
                       INSERT INTO football_brief.campaign_task_attempts
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
                       WHERE task.graph_id=%s AND task.stage_order=%s AND task.status='queued'
                       RETURNING *
                   )
                   UPDATE football_brief.campaign_tasks task
                   SET status='succeeded',attempt_count=attempt.attempt_number,
                       output_fingerprint=attempt.output_fingerprint,
                       output_payload=attempt.output_payload,
                       terminal_fingerprint=attempt.terminal_fingerprint,
                       finished_at=attempt.finished_at,
                       current_attempt_id=NULL,current_worker_id=NULL,current_lease_token=NULL,
                       heartbeat_at=NULL,lease_expires_at=NULL
                   FROM inserted attempt
                   WHERE attempt.task_id=task.id""",
                (graph_id, stage_order),
            )
            total += max(0, cursor.rowcount)
            if stage_order == 1:
                conn.execute(
                    """UPDATE football_brief.campaign_tasks dependent
                       SET status='queued',available_at=now()
                       WHERE dependent.graph_id=%s
                         AND dependent.stage_order=2 AND dependent.status='blocked'
                         AND NOT EXISTS (
                             SELECT 1
                             FROM football_brief.campaign_task_dependencies link
                             JOIN football_brief.campaign_tasks prerequisite
                               ON prerequisite.id=link.depends_on_task_id
                             WHERE link.task_id=dependent.id
                               AND prerequisite.status<>'succeeded'
                         )""",
                    (graph_id,),
                )
    return total


def main() -> int:
    acceptance._recover_and_restart = _recover_and_restart
    acceptance._terminalize_stage = _terminalize_stage
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
