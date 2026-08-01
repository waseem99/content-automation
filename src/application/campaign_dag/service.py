from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class CampaignDagError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _capabilities(values: Iterable[str]) -> list[str]:
    normalized = sorted({str(value).strip().lower() for value in values if str(value).strip()})
    if not normalized:
        raise CampaignDagError("worker_capabilities_required")
    return normalized


class CampaignDagService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def register_worker(
        self,
        *,
        worker_id: str,
        display_name: str,
        capabilities: Iterable[str],
        max_concurrency: int,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not 1 <= max_concurrency <= 1000:
            raise CampaignDagError("invalid_worker_concurrency")
        normalized = _capabilities(capabilities)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            row = conn.execute(
                """INSERT INTO football_brief.campaign_task_workers
                   (worker_id,display_name,capabilities,max_concurrency,metadata,registered_by)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (worker_id) DO UPDATE SET
                     display_name=EXCLUDED.display_name,
                     capabilities=EXCLUDED.capabilities,
                     max_concurrency=EXCLUDED.max_concurrency,
                     metadata=EXCLUDED.metadata,
                     active=true,heartbeat_at=now(),updated_at=now()
                   RETURNING *""",
                (worker_id, display_name, normalized, max_concurrency, _json(metadata or {}), actor),
            ).fetchone()
        return {"ok": True, "worker": dict(row)}

    def heartbeat(self, *, worker_id: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """UPDATE football_brief.campaign_task_workers
                   SET heartbeat_at=now(),updated_at=now()
                   WHERE worker_id=%s AND active=true RETURNING *""",
                (worker_id,),
            ).fetchone()
            if row is None:
                raise CampaignDagError("worker_not_found_or_inactive")
            conn.execute(
                """UPDATE football_brief.campaign_task_attempts attempt
                   SET heartbeat_at=now(),lease_expires_at=now()+interval '5 minutes'
                   FROM football_brief.campaign_tasks task
                   WHERE task.current_attempt_id=attempt.id
                     AND task.current_worker_id=%s
                     AND task.status='running'
                     AND attempt.status='running'""",
                (worker_id,),
            )
            conn.execute(
                """UPDATE football_brief.campaign_tasks
                   SET heartbeat_at=now(),lease_expires_at=now()+interval '5 minutes'
                   WHERE current_worker_id=%s AND status='running'""",
                (worker_id,),
            )
        return {"ok": True, "worker": dict(row)}

    def create_graph(
        self,
        *,
        campaign_id: UUID,
        graph_key: str,
        definition: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        digest = _sha(definition)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            campaign = conn.execute(
                "SELECT id FROM football_brief.production_campaigns WHERE id=%s",
                (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise CampaignDagError("campaign_not_found")
            version = int(
                conn.execute(
                    "SELECT COALESCE(max(version),0)+1 AS value FROM football_brief.campaign_task_graphs WHERE campaign_id=%s",
                    (campaign_id,),
                ).fetchone()["value"]
            )
            row = conn.execute(
                """INSERT INTO football_brief.campaign_task_graphs
                   (campaign_id,version,graph_key,status,definition_sha256,configuration,created_by)
                   VALUES (%s,%s,%s,'draft',%s,%s::jsonb,%s) RETURNING *""",
                (campaign_id, version, graph_key, digest, _json(definition), actor),
            ).fetchone()
            self._event(conn, graph_id=row["id"], event_type="graph_created", actor=actor,
                        details={"definition_sha256": digest, "version": version})
        return {"ok": True, "graph": dict(row)}

    def activate_graph(self, *, graph_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            graph = conn.execute(
                "SELECT * FROM football_brief.campaign_task_graphs WHERE id=%s FOR UPDATE",
                (graph_id,),
            ).fetchone()
            if graph is None:
                raise CampaignDagError("graph_not_found")
            if graph["status"] != "draft":
                raise CampaignDagError("graph_not_draft")
            row = conn.execute(
                """UPDATE football_brief.campaign_task_graphs
                   SET status='active',activated_by=%s,activated_at=now()
                   WHERE id=%s RETURNING *""",
                (actor, graph_id),
            ).fetchone()
            self._event(conn, graph_id=graph_id, event_type="graph_activated", actor=actor, details={})
        return {"ok": True, "graph": dict(row)}

    def set_graph_state(self, *, graph_id: UUID, action: str, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            graph = conn.execute(
                "SELECT * FROM football_brief.campaign_task_graphs WHERE id=%s FOR UPDATE",
                (graph_id,),
            ).fetchone()
            if graph is None:
                raise CampaignDagError("graph_not_found")
            if action == "pause" and graph["status"] == "active":
                row = conn.execute(
                    """UPDATE football_brief.campaign_task_graphs
                       SET status='paused',paused_by=%s,paused_at=now() WHERE id=%s RETURNING *""",
                    (actor, graph_id),
                ).fetchone()
                event = "graph_paused"
            elif action == "resume" and graph["status"] == "paused":
                row = conn.execute(
                    """UPDATE football_brief.campaign_task_graphs
                       SET status='active',paused_by=NULL,paused_at=NULL WHERE id=%s RETURNING *""",
                    (graph_id,),
                ).fetchone()
                event = "graph_resumed"
            elif action == "cancel" and graph["status"] in {"active", "paused", "cancel_requested"}:
                conn.execute(
                    """UPDATE football_brief.campaign_tasks
                       SET status='cancelled',cancel_requested=true,finished_at=now(),
                           terminal_fingerprint=encode(digest((id::text || ':cancelled')::bytea,'sha256'),'hex'),
                           current_attempt_id=NULL,current_worker_id=NULL,current_lease_token=NULL,
                           heartbeat_at=NULL,lease_expires_at=NULL
                       WHERE graph_id=%s AND status IN ('blocked','queued')""",
                    (graph_id,),
                )
                row = conn.execute(
                    """UPDATE football_brief.campaign_task_graphs
                       SET status='cancelled',cancelled_by=%s,cancelled_at=now()
                       WHERE id=%s RETURNING *""",
                    (actor, graph_id),
                ).fetchone()
                event = "graph_cancelled"
            else:
                raise CampaignDagError("invalid_graph_state_transition", details={"status": graph["status"], "action": action})
            self._event(conn, graph_id=graph_id, event_type=event, actor=actor, details={})
        return {"ok": True, "graph": dict(row)}

    def add_task(
        self,
        *,
        graph_id: UUID,
        task_key: str,
        task_type: str,
        required_capabilities: Iterable[str],
        input_payload: dict[str, Any],
        actor: str,
        stage_order: int = 1,
        priority: int = 0,
        max_attempts: int = 3,
        campaign_item_id: UUID | None = None,
        depends_on_task_ids: Iterable[int] = (),
    ) -> dict[str, Any]:
        capabilities = _capabilities(required_capabilities)
        fingerprint = _sha(input_payload)
        idempotency_key = f"p128:{graph_id}:{task_key}:{fingerprint}"
        dependencies = sorted({int(value) for value in depends_on_task_ids})
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            graph = conn.execute(
                "SELECT status FROM football_brief.campaign_task_graphs WHERE id=%s FOR UPDATE",
                (graph_id,),
            ).fetchone()
            if graph is None:
                raise CampaignDagError("graph_not_found")
            if graph["status"] not in {"draft", "active"}:
                raise CampaignDagError("graph_not_editable")
            status = "blocked" if dependencies else "queued"
            row = conn.execute(
                """INSERT INTO football_brief.campaign_tasks
                   (graph_id,campaign_item_id,task_key,task_type,stage_order,required_capabilities,
                    status,priority,idempotency_key,input_fingerprint,input_payload,max_attempts)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
                   ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key=EXCLUDED.idempotency_key
                   RETURNING *""",
                (graph_id, campaign_item_id, task_key, task_type, stage_order, capabilities,
                 status, priority, idempotency_key, fingerprint, _json(input_payload), max_attempts),
            ).fetchone()
            for dependency_id in dependencies:
                dep = conn.execute(
                    "SELECT graph_id FROM football_brief.campaign_tasks WHERE id=%s",
                    (dependency_id,),
                ).fetchone()
                if dep is None or dep["graph_id"] != graph_id:
                    raise CampaignDagError("dependency_not_in_graph", details={"task_id": dependency_id})
                conn.execute(
                    """INSERT INTO football_brief.campaign_task_dependencies(task_id,depends_on_task_id)
                       VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                    (row["id"], dependency_id),
                )
        return {"ok": True, "task": dict(row)}

    def claim(
        self,
        *,
        worker_id: str,
        limit: int = 25,
        lease_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise CampaignDagError("invalid_claim_limit")
        if not 30 <= lease_seconds <= 3600:
            raise CampaignDagError("invalid_lease_seconds")
        with self.database.transaction() as conn:
            worker = conn.execute(
                """SELECT * FROM football_brief.campaign_task_workers
                   WHERE worker_id=%s AND active=true FOR UPDATE""",
                (worker_id,),
            ).fetchone()
            if worker is None:
                raise CampaignDagError("worker_not_found_or_inactive")
            running = int(
                conn.execute(
                    "SELECT count(*)::int AS value FROM football_brief.campaign_tasks WHERE current_worker_id=%s AND status='running'",
                    (worker_id,),
                ).fetchone()["value"]
            )
            remaining = min(limit, int(worker["max_concurrency"]) - running)
            if remaining <= 0:
                return []
            graph_count = int(
                conn.execute(
                    """SELECT count(DISTINCT task.graph_id)::int AS value
                       FROM football_brief.campaign_tasks task
                       JOIN football_brief.campaign_task_graphs graph ON graph.id=task.graph_id
                       WHERE task.status='queued' AND task.available_at<=now()
                         AND graph.status='active'
                         AND task.required_capabilities <@ %s::text[]""",
                    (list(worker["capabilities"]),),
                ).fetchone()["value"]
            )
            if graph_count == 0:
                return []
            per_graph = max(1, (remaining + graph_count - 1) // graph_count)
            candidates = conn.execute(
                """WITH active_graphs AS (
                       SELECT DISTINCT graph.id
                       FROM football_brief.campaign_task_graphs graph
                       JOIN football_brief.campaign_tasks task ON task.graph_id=graph.id
                       WHERE graph.status='active' AND task.status='queued'
                         AND task.available_at<=now()
                         AND task.required_capabilities <@ %s::text[]
                       ORDER BY graph.id
                   ), selected AS (
                       SELECT candidate.id
                       FROM active_graphs graph
                       CROSS JOIN LATERAL (
                           SELECT task.id
                           FROM football_brief.campaign_tasks task
                           WHERE task.graph_id=graph.id
                             AND task.status='queued'
                             AND task.available_at<=now()
                             AND task.required_capabilities <@ %s::text[]
                             AND NOT EXISTS (
                                 SELECT 1
                                 FROM football_brief.campaign_task_dependencies dependency
                                 JOIN football_brief.campaign_tasks prerequisite
                                   ON prerequisite.id=dependency.depends_on_task_id
                                 WHERE dependency.task_id=task.id
                                   AND prerequisite.status<>'succeeded'
                             )
                           ORDER BY task.priority DESC,task.stage_order,task.id
                           FOR UPDATE OF task SKIP LOCKED
                           LIMIT %s
                       ) candidate
                       LIMIT %s
                   )
                   SELECT task.* FROM football_brief.campaign_tasks task
                   JOIN selected ON selected.id=task.id
                   ORDER BY task.graph_id,task.priority DESC,task.id""",
                (list(worker["capabilities"]), list(worker["capabilities"]), per_graph, remaining),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for task in candidates:
                attempt_number = int(task["attempt_count"]) + 1
                attempt = conn.execute(
                    """INSERT INTO football_brief.campaign_task_attempts
                       (task_id,attempt_number,worker_id,input_fingerprint,lease_expires_at)
                       VALUES (%s,%s,%s,%s,now()+(%s || ' seconds')::interval)
                       RETURNING *""",
                    (task["id"], attempt_number, worker_id, task["input_fingerprint"], lease_seconds),
                ).fetchone()
                updated = conn.execute(
                    """UPDATE football_brief.campaign_tasks
                       SET status='running',attempt_count=%s,current_attempt_id=%s,
                           current_worker_id=%s,current_lease_token=%s,
                           heartbeat_at=now(),lease_expires_at=%s,
                           started_at=COALESCE(started_at,now())
                       WHERE id=%s RETURNING *""",
                    (attempt_number, attempt["id"], worker_id, attempt["lease_token"],
                     attempt["lease_expires_at"], task["id"]),
                ).fetchone()
                claimed.append({**dict(updated), "attempt": dict(attempt)})
            if candidates:
                graph_ids = {row["graph_id"] for row in candidates}
                for graph_id in graph_ids:
                    self._event(conn, graph_id=graph_id, event_type="tasks_claimed", actor=worker_id,
                                details={"count": sum(1 for row in candidates if row["graph_id"] == graph_id)})
        return claimed

    def complete(
        self,
        *,
        task_id: int,
        lease_token: UUID,
        output_payload: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        output_fingerprint = _sha(output_payload)
        terminal_fingerprint = _sha({"task_id": task_id, "status": "succeeded", "output": output_fingerprint})
        with self.database.transaction() as conn:
            task = conn.execute(
                "SELECT * FROM football_brief.campaign_tasks WHERE id=%s FOR UPDATE",
                (task_id,),
            ).fetchone()
            if task is None:
                raise CampaignDagError("task_not_found")
            if task["status"] == "succeeded":
                if task["terminal_fingerprint"] != terminal_fingerprint:
                    raise CampaignDagError("terminal_output_conflict")
                return {"ok": True, "idempotent": True, "task": dict(task)}
            if task["status"] != "running" or str(task["current_lease_token"]) != str(lease_token):
                raise CampaignDagError("task_lease_lost")
            attempt = conn.execute(
                "SELECT * FROM football_brief.campaign_task_attempts WHERE id=%s FOR UPDATE",
                (task["current_attempt_id"],),
            ).fetchone()
            if attempt is None or attempt["status"] != "running":
                raise CampaignDagError("running_attempt_not_found")
            conn.execute(
                """UPDATE football_brief.campaign_task_attempts
                   SET status='succeeded',output_fingerprint=%s,terminal_fingerprint=%s,
                       output_payload=%s::jsonb,finished_at=now()
                   WHERE id=%s""",
                (output_fingerprint, terminal_fingerprint, _json(output_payload), attempt["id"]),
            )
            row = conn.execute(
                """UPDATE football_brief.campaign_tasks
                   SET status='succeeded',output_fingerprint=%s,output_payload=%s::jsonb,
                       terminal_fingerprint=%s,finished_at=now(),
                       current_attempt_id=NULL,current_worker_id=NULL,current_lease_token=NULL,
                       heartbeat_at=NULL,lease_expires_at=NULL
                   WHERE id=%s RETURNING *""",
                (output_fingerprint, _json(output_payload), terminal_fingerprint, task_id),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.campaign_tasks dependent
                   SET status='queued',available_at=now()
                   WHERE dependent.status='blocked'
                     AND EXISTS (
                         SELECT 1 FROM football_brief.campaign_task_dependencies link
                         WHERE link.task_id=dependent.id AND link.depends_on_task_id=%s
                     )
                     AND NOT EXISTS (
                         SELECT 1
                         FROM football_brief.campaign_task_dependencies link
                         JOIN football_brief.campaign_tasks prerequisite ON prerequisite.id=link.depends_on_task_id
                         WHERE link.task_id=dependent.id AND prerequisite.status<>'succeeded'
                     )""",
                (task_id,),
            )
            self._event(conn, graph_id=task["graph_id"], task_id=task_id,
                        attempt_id=attempt["id"], event_type="tasks_completed", actor=actor,
                        details={"terminal_fingerprint": terminal_fingerprint})
            remaining = int(
                conn.execute(
                    "SELECT count(*)::int AS value FROM football_brief.campaign_tasks WHERE graph_id=%s AND status NOT IN ('succeeded','cancelled','dead_letter')",
                    (task["graph_id"],),
                ).fetchone()["value"]
            )
            if remaining == 0:
                conn.execute(
                    """UPDATE football_brief.campaign_task_graphs
                       SET status='completed',completed_at=now() WHERE id=%s AND status='active'""",
                    (task["graph_id"],),
                )
                self._event(conn, graph_id=task["graph_id"], event_type="graph_completed", actor=actor, details={})
        return {"ok": True, "idempotent": False, "task": dict(row)}

    def recover_stale_leases(self, *, actor: str, limit: int = 1000) -> dict[str, Any]:
        if not 1 <= limit <= 10000:
            raise CampaignDagError("invalid_recovery_limit")
        with self.database.transaction() as conn:
            stale = conn.execute(
                """SELECT * FROM football_brief.campaign_tasks
                   WHERE status='running' AND lease_expires_at<now()
                   ORDER BY lease_expires_at,id FOR UPDATE SKIP LOCKED LIMIT %s""",
                (limit,),
            ).fetchall()
            recovered = 0
            dead_lettered = 0
            for task in stale:
                attempt = conn.execute(
                    "SELECT * FROM football_brief.campaign_task_attempts WHERE id=%s FOR UPDATE",
                    (task["current_attempt_id"],),
                ).fetchone()
                if attempt and attempt["status"] == "running":
                    conn.execute(
                        """UPDATE football_brief.campaign_task_attempts
                           SET status='timed_out',error_code='lease_expired',finished_at=now()
                           WHERE id=%s""",
                        (attempt["id"],),
                    )
                terminal = int(task["attempt_count"]) >= int(task["max_attempts"])
                if terminal:
                    fingerprint = _sha({"task_id": task["id"], "status": "dead_letter", "attempts": task["attempt_count"]})
                    conn.execute(
                        """UPDATE football_brief.campaign_tasks
                           SET status='dead_letter',terminal_fingerprint=%s,finished_at=now(),
                               error_code='max_attempts_exhausted',current_attempt_id=NULL,
                               current_worker_id=NULL,current_lease_token=NULL,
                               heartbeat_at=NULL,lease_expires_at=NULL WHERE id=%s""",
                        (fingerprint, task["id"]),
                    )
                    dead_lettered += 1
                else:
                    conn.execute(
                        """UPDATE football_brief.campaign_tasks
                           SET status='queued',available_at=now(),current_attempt_id=NULL,
                               current_worker_id=NULL,current_lease_token=NULL,
                               heartbeat_at=NULL,lease_expires_at=NULL,
                               error_code='lease_recovered'
                           WHERE id=%s""",
                        (task["id"],),
                    )
                    recovered += 1
                self._event(conn, graph_id=task["graph_id"], task_id=task["id"],
                            attempt_id=attempt["id"] if attempt else None,
                            event_type="leases_recovered", actor=actor,
                            details={"dead_lettered": terminal})
        return {"ok": True, "recovered": recovered, "dead_lettered": dead_lettered}

    def summary(self, *, graph_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            graph = conn.execute(
                "SELECT * FROM football_brief.campaign_task_graphs WHERE id=%s",
                (graph_id,),
            ).fetchone()
            if graph is None:
                raise CampaignDagError("graph_not_found")
            rows = conn.execute(
                """SELECT status,count(*)::bigint AS count
                   FROM football_brief.campaign_tasks WHERE graph_id=%s GROUP BY status""",
                (graph_id,),
            ).fetchall()
        return {"ok": True, "graph": dict(graph), "counts": {row["status"]: row["count"] for row in rows}}

    @staticmethod
    def _require_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if row is None:
            raise CampaignDagError("operator_inactive_or_missing")

    @staticmethod
    def _event(
        conn: Any,
        *,
        graph_id: UUID,
        event_type: str,
        actor: str,
        details: dict[str, Any],
        task_id: int | None = None,
        attempt_id: int | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.campaign_task_events
               (graph_id,task_id,attempt_id,event_type,actor,details)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
            (graph_id, task_id, attempt_id, event_type, actor, _json(details)),
        )


__all__ = ["CampaignDagError", "CampaignDagService"]
