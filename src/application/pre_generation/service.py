from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from src.application.scripts.models import ScriptDecision
from src.application.scripts.service import ScriptReviewError, ScriptReviewService
from src.operator_api.p110_runtime import P110CreateContentRequest, P110Error, P110Service

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


RULE_VERSION = "p120-v1"
TERMINAL_STATUSES = {"human_exception", "hard_block", "ready", "failed", "cancelled"}


class PreGenerationError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PreGenerationService:
    """Automatic campaign progression up to final video generation.

    The service reuses the existing P110 content-family and script-generation
    systems. It does not render video, approve paid spend or publish content.
    """

    def __init__(self, database: "Database") -> None:
        self.database = database
        self.p110 = P110Service(database)
        self.scripts = ScriptReviewService(database)

    def ensure_runs(self, *, campaign_id: UUID | None = None, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            conditions = ["item.state='activated'", "version.status='active'", "campaign.status='active'"]
            values: list[Any] = []
            if campaign_id is not None:
                conditions.append("campaign.id=%s")
                values.append(campaign_id)
            inserted = conn.execute(
                f"""INSERT INTO football_brief.pre_generation_runs
                    (campaign_item_id,autopilot_policy_id,status,current_stage,metadata)
                    SELECT item.id,version.autopilot_policy_id,'queued','content_expansion',
                           jsonb_build_object('created_by',%s,'campaign_id',campaign.id::text)
                    FROM football_brief.production_campaign_items item
                    JOIN football_brief.production_campaign_versions version
                      ON version.id=item.campaign_version_id
                    JOIN football_brief.production_campaigns campaign
                      ON campaign.id=version.campaign_id
                    WHERE {' AND '.join(conditions)}
                    ON CONFLICT (campaign_item_id) DO NOTHING
                    RETURNING id""",
                (actor, *values),
            ).fetchall()
        return {
            "ok": True,
            "kind": "pre_generation_runs_ensured",
            "campaign_id": str(campaign_id) if campaign_id else None,
            "created": len(inserted),
        }

    def claim(self, *, owner: str, limit: int = 25, lease_seconds: int = 300) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise PreGenerationError("invalid_claim_limit")
        if not 30 <= lease_seconds <= 3600:
            raise PreGenerationError("invalid_lease_seconds")
        token = uuid4()
        with self.database.transaction() as conn:
            rows = conn.execute(
                """WITH candidates AS (
                       SELECT run.id
                       FROM football_brief.pre_generation_runs run
                       JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                       JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                       JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
                       WHERE run.status IN ('queued','running','waiting')
                         AND run.next_attempt_at<=now()
                         AND (run.lease_expires_at IS NULL OR run.lease_expires_at<now())
                         AND campaign.status='active'
                         AND version.status='active'
                         AND item.state IN ('activated','auto_progressing')
                       ORDER BY item.priority DESC,item.ordinal,run.created_at
                       FOR UPDATE OF run SKIP LOCKED
                       LIMIT %s
                   )
                   UPDATE football_brief.pre_generation_runs run
                   SET status='running',lease_owner=%s,lease_token=%s,
                       lease_expires_at=now()+(%s || ' seconds')::interval,
                       started_at=COALESCE(started_at,now()),updated_at=now()
                   FROM candidates
                   WHERE run.id=candidates.id
                   RETURNING run.*""",
                (limit, owner, token, lease_seconds),
            ).fetchall()
        return [dict(row) for row in rows]

    def process_claim(
        self,
        *,
        run_id: UUID,
        lease_token: UUID,
        actor: str,
        max_steps: int = 12,
    ) -> dict[str, Any]:
        if not 1 <= max_steps <= 20:
            raise PreGenerationError("invalid_max_steps")
        outcome: dict[str, Any] = {"ok": True, "run_id": str(run_id)}
        for _ in range(max_steps):
            run = self._owned_run(run_id=run_id, lease_token=lease_token)
            if run["status"] in TERMINAL_STATUSES:
                return {**outcome, "status": run["status"], "stage": run["current_stage"]}
            stage = str(run["current_stage"])
            if stage == "content_expansion":
                outcome = self._content_expansion(run=run, lease_token=lease_token, actor=actor)
            elif stage == "script_generation":
                outcome = self._script_generation(run=run, lease_token=lease_token, actor=actor)
            elif stage == "script_checks":
                outcome = self._script_checks(run=run, lease_token=lease_token, actor=actor)
            elif stage == "script_approval":
                outcome = self._script_approval(run=run, lease_token=lease_token, actor=actor)
            elif stage in {"narration_plan", "scene_plan", "caption_package"}:
                outcome = self._planning_stage(run=run, lease_token=lease_token, actor=actor, stage=stage)
            elif stage == "final_generation_package":
                outcome = self._final_package(run=run, lease_token=lease_token, actor=actor)
            elif stage == "complete":
                return {**outcome, "status": "ready", "stage": "complete"}
            else:
                return self._system_failure(
                    run=run,
                    lease_token=lease_token,
                    actor=actor,
                    code="unsupported_pre_generation_stage",
                    details={"stage": stage},
                )
            if outcome.get("waiting") or outcome.get("terminal"):
                return outcome
        return self._release_waiting(
            run_id=run_id,
            lease_token=lease_token,
            seconds=1,
            details={"reason": "max_steps_reached"},
        )

    def dashboard(self, *, campaign_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            campaign = conn.execute(
                """SELECT c.*,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.production_campaigns c
                   JOIN football_brief.brands b ON b.id=c.brand_id
                   WHERE c.id=%s""",
                (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise PreGenerationError("campaign_not_found")
            states = conn.execute(
                """SELECT item.state,count(*)::int AS count
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s
                   GROUP BY item.state ORDER BY item.state""",
                (campaign_id,),
            ).fetchall()
            stages = conn.execute(
                """SELECT run.current_stage,run.status,count(*)::int AS count
                   FROM football_brief.pre_generation_runs run
                   JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s
                   GROUP BY run.current_stage,run.status
                   ORDER BY run.current_stage,run.status""",
                (campaign_id,),
            ).fetchall()
            exceptions = conn.execute(
                """SELECT exception.category,exception.exception_code,exception.severity,
                          exception.rule_version,count(*)::int AS count,
                          min(exception.created_at) AS oldest_at
                   FROM football_brief.pre_generation_exceptions exception
                   JOIN football_brief.pre_generation_runs run ON run.id=exception.run_id
                   JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s AND exception.status='open'
                   GROUP BY exception.category,exception.exception_code,exception.severity,exception.rule_version
                   ORDER BY exception.severity DESC,count(*) DESC,exception.exception_code""",
                (campaign_id,),
            ).fetchall()
            metrics = conn.execute(
                """SELECT count(*)::int AS total,
                          count(*) FILTER (WHERE item.state='ready_for_final_video_generation')::int AS ready,
                          count(*) FILTER (WHERE item.state='human_exception')::int AS human_exception,
                          count(*) FILTER (WHERE item.state='hard_block')::int AS hard_block,
                          count(*) FILTER (WHERE run.correction_count>0)::int AS corrected,
                          avg(run.score)::numeric(6,2) AS average_score
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   LEFT JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   WHERE version.campaign_id=%s""",
                (campaign_id,),
            ).fetchone()
        total = int(metrics["total"] or 0)
        ready = int(metrics["ready"] or 0)
        return {
            "ok": True,
            "kind": "pre_generation_dashboard",
            "campaign": dict(campaign),
            "state_counts": {str(row["state"]): int(row["count"]) for row in states},
            "stage_counts": [dict(row) for row in stages],
            "exceptions": [dict(row) for row in exceptions],
            "metrics": {
                **dict(metrics),
                "automation_rate": round((ready / total) * 100, 2) if total else 0.0,
            },
        }

    def grid(
        self,
        *,
        campaign_id: UUID,
        state: str | None = None,
        exception_code: str | None = None,
        after_ordinal: int | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise PreGenerationError("invalid_grid_limit")
        conditions = ["version.campaign_id=%s"]
        values: list[Any] = [campaign_id]
        if state:
            conditions.append("item.state=%s")
            values.append(state)
        if exception_code:
            conditions.append(
                "EXISTS (SELECT 1 FROM football_brief.pre_generation_exceptions exception "
                "WHERE exception.campaign_item_id=item.id AND exception.status='open' "
                "AND exception.exception_code=%s)"
            )
            values.append(exception_code)
        if after_ordinal is not None:
            conditions.append("item.ordinal>%s")
            values.append(after_ordinal)
        values.append(limit)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT item.id,item.item_key,item.ordinal,item.title,item.topic,item.primary_platform,
                            item.target_platforms,item.target_duration_seconds,item.short_cut_count,
                            item.scheduled_for,item.priority,item.state,item.disposition,
                            item.portfolio_content_id,item.content_family_id,item.updated_at,
                            run.id AS run_id,run.status AS run_status,run.current_stage,run.score,
                            run.correction_count,run.last_error_code,run.next_attempt_at,
                            package.id AS package_id,package.package_sha256,
                            (SELECT count(*) FROM football_brief.pre_generation_exceptions exception
                             WHERE exception.campaign_item_id=item.id AND exception.status='open')::int
                             AS open_exception_count
                     FROM football_brief.production_campaign_items item
                     JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                     LEFT JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                     LEFT JOIN football_brief.pre_generation_packages package
                       ON package.campaign_item_id=item.id AND package.status='ready'
                     WHERE {' AND '.join(conditions)}
                     ORDER BY item.ordinal,item.id
                     LIMIT %s""",
                tuple(values),
            ).fetchall()
        items = [dict(row) for row in rows]
        return {
            "ok": True,
            "kind": "pre_generation_grid",
            "items": items,
            "next_after_ordinal": items[-1]["ordinal"] if len(items) == limit else None,
        }

    def retry_items(self, *, campaign_id: UUID, item_ids: list[UUID], actor: str) -> dict[str, Any]:
        if not item_ids or len(item_ids) > 1000:
            raise PreGenerationError("retry_selection_must_contain_1_to_1000_items")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            action = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,requested_by,started_at)
                   VALUES (%s,'retry','running',%s::jsonb,%s,%s,now()) RETURNING *""",
                (campaign_id, _json({"item_ids": [str(value) for value in item_ids]}), len(item_ids), actor),
            ).fetchone()
            updated = conn.execute(
                """UPDATE football_brief.pre_generation_runs run
                   SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                       next_attempt_at=now(),last_error_code=NULL,last_error_detail='{}'::jsonb,updated_at=now()
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE run.campaign_item_id=item.id AND version.campaign_id=%s
                     AND item.id=ANY(%s::uuid[])
                     AND run.status IN ('human_exception','hard_block','failed','waiting')
                   RETURNING run.id,item.id""",
                (campaign_id, item_ids),
            ).fetchall()
            if updated:
                conn.execute(
                    """UPDATE football_brief.production_campaign_items
                       SET state='auto_progressing',disposition=NULL,updated_at=now()
                       WHERE id=ANY(%s::uuid[])""",
                    ([row["id"] for row in updated],),
                )
            conn.execute(
                """UPDATE football_brief.pre_generation_exceptions exception
                   SET status='superseded',resolved_at=now(),resolved_by=%s,
                       resolution=jsonb_build_object('action','retry')
                   WHERE exception.campaign_item_id=ANY(%s::uuid[]) AND exception.status='open'""",
                (actor, item_ids),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_actions
                   SET status=%s,succeeded_count=%s,failed_count=%s,completed_at=now(),
                       result=%s::jsonb WHERE id=%s""",
                (
                    "completed" if len(updated) == len(item_ids) else "partial",
                    len(updated),
                    len(item_ids) - len(updated),
                    _json({"retried_run_ids": [str(row["id"]) for row in updated]}),
                    action["id"],
                ),
            )
        return {
            "ok": True,
            "kind": "pre_generation_retry",
            "requested": len(item_ids),
            "retried": len(updated),
            "action_id": str(action["id"]),
        }

    def _content_expansion(self, *, run: dict[str, Any], lease_token: UUID, actor: str) -> dict[str, Any]:
        context = self._context(run["id"])
        if context["portfolio_content_id"]:
            return self._advance(
                run_id=run["id"],
                lease_token=lease_token,
                stage="script_generation",
                actor=actor,
                details={"reused_content_id": str(context["portfolio_content_id"])},
            )
        request = P110CreateContentRequest(
            brand_id=UUID(str(context["brand_id"])),
            title=str(context["title"]),
            topic=str(context["topic"]),
            objective=str(context["objective"] or ""),
            audience=str(context["audience"] or ""),
            platform=str(context["primary_platform"]),
            primary_platform=str(context["primary_platform"]),
            target_platforms=list(context["target_platforms"] or []),
            format_name=str(context["format_name"]),
            duration_seconds=int(context["target_duration_seconds"]),
            short_cut_count=int(context["short_cut_count"]),
            language=str(context["language"]),
            scheduled_for=context["scheduled_for"] if isinstance(context["scheduled_for"], date) else date.fromisoformat(str(context["scheduled_for"])),
            notes=f"Database-native campaign item {context['item_key']}",
            generate_script=True,
            starting_point="approved_plan",
        )
        try:
            created = self.p110.create_content(request, actor=actor)
        except (P110Error, HTTPException, ValueError) as exc:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="content_expansion_failed",
                category="system",
                severity="human_exception",
                details={"error": str(exc), "type": type(exc).__name__},
            )
        content_id = UUID(str(created["content_id"]))
        family_id = UUID(str(created["family"]["content_family_id"]))
        with self.database.transaction() as conn:
            owned = self._owned_run_locked(conn, run["id"], lease_token)
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='auto_progressing',portfolio_content_id=%s,content_family_id=%s,
                       updated_at=now(),metadata=metadata || %s::jsonb
                   WHERE id=%s""",
                (
                    content_id,
                    family_id,
                    _json({"p120": {"expanded_by": actor, "workflow_id": created.get("workflow_id")}}),
                    owned["campaign_item_id"],
                ),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET portfolio_content_id=%s,current_stage='script_generation',stage_attempt=0,
                       status='running',updated_at=now() WHERE id=%s""",
                (content_id, run["id"]),
            )
            self._event(
                conn,
                item_id=owned["campaign_item_id"],
                event_type="content_family_expanded",
                from_state="activated",
                to_state="auto_progressing",
                actor=actor,
                details={"content_id": str(content_id), "content_family_id": str(family_id)},
            )
        return {"ok": True, "run_id": str(run["id"]), "stage": "script_generation"}

    def _script_generation(self, *, run: dict[str, Any], lease_token: UUID, actor: str) -> dict[str, Any]:
        context = self._context(run["id"])
        content_id = context["portfolio_content_id"]
        if not content_id:
            return self._system_failure(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="portfolio_content_missing_after_expansion",
                details={},
            )
        with self.database.connection() as conn:
            document = conn.execute(
                """SELECT sd.id,sd.lock_version,sv.status,sv.id AS script_version_id
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   WHERE sd.portfolio_content_id=%s""",
                (content_id,),
            ).fetchone()
            job = conn.execute(
                """SELECT id,status,error_code,error_message,attempt_count,max_attempts
                   FROM football_brief.generation_jobs
                   WHERE portfolio_content_id=%s AND job_type='script'
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
        if document:
            with self.database.transaction() as conn:
                self._owned_run_locked(conn, run["id"], lease_token)
                conn.execute(
                    """UPDATE football_brief.pre_generation_runs
                       SET script_document_id=%s,current_stage='script_checks',stage_attempt=0,
                           status='running',updated_at=now() WHERE id=%s""",
                    (document["id"], run["id"]),
                )
            return {"ok": True, "run_id": str(run["id"]), "stage": "script_checks"}
        if job and str(job["status"]) in {"failed", "dead_letter", "cancelled"}:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="script_generation_failed",
                category="system",
                severity="human_exception",
                details=dict(job),
            )
        return self._release_waiting(
            run_id=run["id"],
            lease_token=lease_token,
            seconds=5,
            details={"waiting_for": "script_job", "job": dict(job) if job else None},
        )

    def _script_checks(self, *, run: dict[str, Any], lease_token: UUID, actor: str) -> dict[str, Any]:
        context = self._context(run["id"])
        document_id = context["script_document_id"]
        if not document_id:
            return self._advance(
                run_id=run["id"],
                lease_token=lease_token,
                stage="script_generation",
                actor=actor,
                details={"reason": "script_document_not_bound"},
            )
        try:
            detail = self.scripts.detail(document_id=UUID(str(document_id)))
        except ScriptReviewError as exc:
            return self._system_failure(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code=exc.code,
                details=exc.details,
            )
        document = detail["document"]
        current_id = str(document["current_version_id"])
        version = next(row for row in detail["versions"] if str(row["id"]) == current_id)
        scenes = [row for row in detail["scenes"] if str(row["script_version_id"]) == current_id]
        claims = [row for row in detail["claims"] if str(row["script_version_id"]) == current_id]
        sources = [row for row in detail["sources"] if str(row["script_version_id"]) == current_id]
        target = float(version["target_duration_seconds"] or context["target_duration_seconds"] or 1)
        estimated = float(version["estimated_duration_seconds"] or 0)
        tolerance = float(version["duration_tolerance_percent"] or 10)
        duration_delta = abs(estimated - target) / max(target, 1) * 100
        unsupported = [
            row for row in claims
            if str(row.get("claim_type")) == "factual" and str(row.get("support_status")) != "supported"
        ]
        duplicate_count = self._approved_fingerprint_count(
            brand_id=UUID(str(context["brand_id"])),
            fingerprint=str(version["content_fingerprint"]),
            current_version_id=UUID(current_id),
        )
        prohibited = self._prohibited_matches(
            text=str(version["full_text"] or ""),
            restrictions=context.get("content_restrictions") or {},
        )
        checks = [
            {
                "key": "script_structure",
                "passed": bool(version["full_text"] and scenes and version["hook_text"] and version["cta_text"]),
                "score": 25,
                "evidence": {"scene_count": len(scenes), "word_count": version["word_count"]},
            },
            {
                "key": "duration_fit",
                "passed": duration_delta <= tolerance,
                "score": 20,
                "evidence": {"target": target, "estimated": estimated, "delta_percent": duration_delta, "tolerance": tolerance},
            },
            {
                "key": "source_support",
                "passed": not unsupported,
                "score": 25,
                "evidence": {"factual_claims": len([row for row in claims if str(row.get('claim_type')) == 'factual']), "unsupported": [row.get("claim_key") for row in unsupported], "source_count": len(sources)},
            },
            {
                "key": "originality",
                "passed": duplicate_count == 0,
                "score": 15,
                "evidence": {"other_approved_matches": duplicate_count, "content_fingerprint": version["content_fingerprint"]},
            },
            {
                "key": "prohibited_content",
                "passed": not prohibited,
                "score": 15,
                "evidence": {"matches": prohibited},
            },
        ]
        score = Decimal(sum(item["score"] for item in checks if item["passed"]))
        with self.database.transaction() as conn:
            self._owned_run_locked(conn, run["id"], lease_token)
            for check in checks:
                conn.execute(
                    """INSERT INTO football_brief.pre_generation_checks
                       (run_id,stage,check_key,rule_version,status,score,evidence)
                       VALUES (%s,'script_checks',%s,%s,%s,%s,%s::jsonb)
                       ON CONFLICT (run_id,stage,check_key,rule_version) DO UPDATE SET
                         status=EXCLUDED.status,score=EXCLUDED.score,evidence=EXCLUDED.evidence,
                         created_at=now()""",
                    (
                        run["id"],
                        check["key"],
                        RULE_VERSION,
                        "passed" if check["passed"] else "failed",
                        check["score"] if check["passed"] else 0,
                        _json(check["evidence"]),
                    ),
                )
            conn.execute(
                "UPDATE football_brief.pre_generation_runs SET score=%s,updated_at=now() WHERE id=%s",
                (score, run["id"]),
            )
        if prohibited:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="safety_block",
                category="safety",
                severity="hard_block",
                details={"prohibited_matches": prohibited},
            )
        if unsupported:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="source_block",
                category="source",
                severity="hard_block",
                details={"claim_keys": [row.get("claim_key") for row in unsupported]},
            )
        if duplicate_count:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="duplicate_content",
                category="duplication",
                severity="human_exception",
                details={"other_approved_matches": duplicate_count},
            )
        minimum = Decimal(str(context["minimum_auto_score"]))
        if score < minimum or duration_delta > tolerance or not scenes:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="script_quality_below_policy",
                category="structural",
                severity="human_exception",
                details={"score": float(score), "minimum": float(minimum), "duration_delta": duration_delta, "scene_count": len(scenes)},
            )
        return self._advance(
            run_id=run["id"],
            lease_token=lease_token,
            stage="script_approval",
            actor=actor,
            details={"score": float(score), "rule_version": RULE_VERSION},
        )

    def _script_approval(self, *, run: dict[str, Any], lease_token: UUID, actor: str) -> dict[str, Any]:
        context = self._context(run["id"])
        document_id = UUID(str(context["script_document_id"]))
        try:
            detail = self.scripts.detail(document_id=document_id)
            status = str(detail["document"]["current_version_status"])
            lock_version = int(detail["document"]["lock_version"])
            if status == "working":
                detail = self.scripts.submit(document_id=document_id, expected_lock_version=lock_version, actor=actor)
                lock_version = int(detail["document"]["lock_version"])
                status = str(detail["document"]["current_version_status"])
            if status == "in_review":
                detail = self.scripts.decide(
                    document_id=document_id,
                    expected_lock_version=lock_version,
                    decision=ScriptDecision.APPROVED,
                    rationale=f"Automatically approved by pre-generation policy {context['policy_key']} after {RULE_VERSION} checks.",
                    reviewer=actor,
                )
                status = str(detail["document"]["current_version_status"])
        except ScriptReviewError as exc:
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="automatic_script_approval_failed",
                category="system",
                severity="human_exception",
                details={"error_code": exc.code, **exc.details},
            )
        if status != "approved":
            return self._exception(
                run=run,
                lease_token=lease_token,
                actor=actor,
                code="script_not_approved_after_autopilot_decision",
                category="structural",
                severity="human_exception",
                details={"status": status},
            )
        with self.database.transaction() as conn:
            self._owned_run_locked(conn, run["id"], lease_token)
            self._check(
                conn,
                run_id=run["id"],
                stage="script_approval",
                key="automatic_policy_decision",
                status="passed",
                score=100,
                evidence={"policy_id": str(context["autopilot_policy_id"]), "policy_key": context["policy_key"], "reviewer": actor},
            )
        return self._advance(
            run_id=run["id"],
            lease_token=lease_token,
            stage="narration_plan",
            actor=actor,
            details={"script_status": "approved"},
        )

    def _planning_stage(
        self,
        *,
        run: dict[str, Any],
        lease_token: UUID,
        actor: str,
        stage: str,
    ) -> dict[str, Any]:
        context = self._context(run["id"])
        detail = self.scripts.detail(document_id=UUID(str(context["script_document_id"])))
        current_id = str(detail["document"]["current_version_id"])
        version = next(row for row in detail["versions"] if str(row["id"]) == current_id)
        scenes = [row for row in detail["scenes"] if str(row["script_version_id"]) == current_id]
        if stage == "narration_plan":
            evidence = {
                "language": version["language"],
                "target_duration_seconds": float(version["target_duration_seconds"]),
                "estimated_duration_seconds": float(version["estimated_duration_seconds"]),
                "voice_profile": self._voice_profile(str(context["brand_slug"])),
                "narration_preset_id": str(context["narration_preset_id"]) if context.get("narration_preset_id") else None,
                "generated_audio": False,
            }
            next_stage = "scene_plan"
        elif stage == "scene_plan":
            evidence = {
                "scene_count": len(scenes),
                "exact_target_duration_seconds": int(context["target_duration_seconds"]),
                "continuity_binding": {
                    "brand_profile_id": str(context["brand_profile_id"]) if context.get("brand_profile_id") else None,
                    "content_family_id": str(context["content_family_id"]),
                },
                "generated_video": False,
            }
            next_stage = "caption_package"
        else:
            evidence = {
                "title": context["title"],
                "primary_platform": context["primary_platform"],
                "target_platforms": list(context["target_platforms"] or []),
                "caption": self._caption(context, version),
                "hashtags": self._hashtags(str(context["brand_slug"]), str(context["title"])),
                "thumbnail_copy": self._thumbnail_copy(str(context["title"])),
                "published": False,
            }
            next_stage = "final_generation_package"
        with self.database.transaction() as conn:
            self._owned_run_locked(conn, run["id"], lease_token)
            self._check(
                conn,
                run_id=run["id"],
                stage=stage,
                key=f"{stage}_frozen",
                status="passed",
                score=100,
                evidence=evidence,
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET metadata=metadata || %s::jsonb WHERE id=%s""",
                (_json({stage: evidence}), run["id"]),
            )
        return self._advance(
            run_id=run["id"],
            lease_token=lease_token,
            stage=next_stage,
            actor=actor,
            details={"planned_stage": stage},
        )

    def _final_package(self, *, run: dict[str, Any], lease_token: UUID, actor: str) -> dict[str, Any]:
        context = self._context(run["id"])
        detail = self.scripts.detail(document_id=UUID(str(context["script_document_id"])))
        current_id = str(detail["document"]["current_version_id"])
        version = next(row for row in detail["versions"] if str(row["id"]) == current_id)
        package = {
            "schema": "ready-for-final-video-generation/v1",
            "campaign": {
                "id": str(context["campaign_id"]),
                "key": context["campaign_key"],
                "version_id": str(context["campaign_version_id"]),
                "item_id": str(context["campaign_item_id"]),
                "item_key": context["item_key"],
            },
            "brand": {
                "id": str(context["brand_id"]),
                "slug": context["brand_slug"],
                "name": context["brand_name"],
                "profile_id": str(context["brand_profile_id"]) if context.get("brand_profile_id") else None,
            },
            "content_family": {
                "master_content_id": str(context["portfolio_content_id"]),
                "content_family_id": str(context["content_family_id"]),
                "primary_platform": context["primary_platform"],
                "target_platforms": list(context["target_platforms"] or []),
                "target_duration_seconds": context["target_duration_seconds"],
                "short_cut_count": context["short_cut_count"],
            },
            "script": {
                "document_id": str(context["script_document_id"]),
                "version_id": current_id,
                "version": version["version"],
                "status": version["status"],
                "language": version["language"],
                "hook": version["hook_text"],
                "cta": version["cta_text"],
                "full_text": version["full_text"],
                "word_count": version["word_count"],
                "estimated_duration_seconds": float(version["estimated_duration_seconds"]),
                "content_fingerprint": version["content_fingerprint"],
            },
            "sections": [self._plain(row) for row in detail["sections"] if str(row["script_version_id"]) == current_id],
            "scenes": [self._plain(row) for row in detail["scenes"] if str(row["script_version_id"]) == current_id],
            "claims": [self._plain(row) for row in detail["claims"] if str(row["script_version_id"]) == current_id],
            "sources": [self._plain(row) for row in detail["sources"] if str(row["script_version_id"]) == current_id],
            "claim_sources": [self._plain(row) for row in detail["claim_sources"] if str(row["script_version_id"]) == current_id],
            "narration_plan": context.get("run_metadata", {}).get("narration_plan", {}),
            "scene_plan": context.get("run_metadata", {}).get("scene_plan", {}),
            "caption_package": context.get("run_metadata", {}).get("caption_package", {}),
            "routing_constraints": {
                "storage_providers": ["local", "google_drive"],
                "automatic_paid_spend": False,
                "automatic_public_publishing": False,
                "final_video_generation_deferred": True,
            },
            "autopilot": {
                "run_id": str(run["id"]),
                "policy_id": str(context["autopilot_policy_id"]),
                "policy_key": context["policy_key"],
                "policy_version": context["policy_version"],
                "rule_version": RULE_VERSION,
                "score": float(context["run_score"] or 0),
            },
        }
        digest = _sha(package)
        with self.database.transaction() as conn:
            owned = self._owned_run_locked(conn, run["id"], lease_token)
            current = conn.execute(
                """SELECT * FROM football_brief.pre_generation_packages
                   WHERE campaign_item_id=%s AND status='ready' FOR UPDATE""",
                (owned["campaign_item_id"],),
            ).fetchone()
            if current and current["package_sha256"] == digest:
                package_row = current
            else:
                version_number = conn.execute(
                    """SELECT COALESCE(max(version),0)+1 AS value
                       FROM football_brief.pre_generation_packages WHERE campaign_item_id=%s""",
                    (owned["campaign_item_id"],),
                ).fetchone()["value"]
                if current:
                    conn.execute(
                        """UPDATE football_brief.pre_generation_packages
                           SET status='superseded',superseded_at=now() WHERE id=%s""",
                        (current["id"],),
                    )
                package_row = conn.execute(
                    """INSERT INTO football_brief.pre_generation_packages
                       (campaign_item_id,version,status,package_sha256,package,created_by)
                       VALUES (%s,%s,'ready',%s,%s::jsonb,%s) RETURNING *""",
                    (owned["campaign_item_id"], version_number, digest, _json(package), actor),
                ).fetchone()
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='ready_for_final_video_generation',
                       disposition='ready_for_final_video_generation',ready_at=now(),updated_at=now()
                   WHERE id=%s""",
                (owned["campaign_item_id"],),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='ready',current_stage='complete',package_id=%s,completed_at=now(),
                       lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,updated_at=now()
                   WHERE id=%s""",
                (package_row["id"], run["id"]),
            )
            self._event(
                conn,
                item_id=owned["campaign_item_id"],
                event_type="ready_for_final_video_generation",
                from_state="auto_progressing",
                to_state="ready_for_final_video_generation",
                actor=actor,
                details={"package_id": str(package_row["id"]), "package_sha256": digest},
            )
        return {
            "ok": True,
            "terminal": True,
            "status": "ready",
            "stage": "complete",
            "run_id": str(run["id"]),
            "package_id": str(package_row["id"]),
            "package_sha256": digest,
        }

    def _context(self, run_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT run.id AS run_id,run.status AS run_status,run.current_stage,
                          run.portfolio_content_id,run.script_document_id,run.score AS run_score,
                          run.metadata AS run_metadata,run.autopilot_policy_id,
                          policy.version AS policy_version,policy.policy_key,policy.minimum_auto_score,
                          policy.max_auto_corrections,policy.configuration AS policy_configuration,
                          item.id AS campaign_item_id,item.item_key,item.title,item.topic,item.objective,
                          item.audience,item.format_name,item.primary_platform,item.target_platforms,
                          item.target_duration_seconds,item.short_cut_count,item.language,item.scheduled_for,
                          item.priority,item.content_family_id,item.metadata AS item_metadata,
                          version.id AS campaign_version_id,version.campaign_id,
                          campaign.campaign_key,campaign.brand_id,
                          brand.slug AS brand_slug,brand.display_name AS brand_name,
                          content.brand_profile_id,content.narration_preset_id,
                          COALESCE(profile.content_restrictions,'{}'::jsonb) AS content_restrictions
                   FROM football_brief.pre_generation_runs run
                   JOIN football_brief.pre_generation_autopilot_policies policy ON policy.id=run.autopilot_policy_id
                   JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
                   JOIN football_brief.brands brand ON brand.id=campaign.brand_id
                   LEFT JOIN football_brief.portfolio_content content ON content.id=run.portfolio_content_id
                   LEFT JOIN football_brief.brand_profiles profile
                     ON profile.id=content.brand_profile_id
                   WHERE run.id=%s""",
                (run_id,),
            ).fetchone()
        if row is None:
            raise PreGenerationError("pre_generation_run_not_found")
        return dict(row)

    def _owned_run(self, *, run_id: UUID, lease_token: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT * FROM football_brief.pre_generation_runs
                   WHERE id=%s AND lease_token=%s AND lease_expires_at>now()""",
                (run_id, lease_token),
            ).fetchone()
        if row is None:
            raise PreGenerationError("pre_generation_lease_lost")
        return dict(row)

    @staticmethod
    def _owned_run_locked(conn: Any, run_id: UUID, lease_token: UUID) -> dict[str, Any]:
        row = conn.execute(
            """SELECT * FROM football_brief.pre_generation_runs
               WHERE id=%s AND lease_token=%s AND lease_expires_at>now()
               FOR UPDATE""",
            (run_id, lease_token),
        ).fetchone()
        if row is None:
            raise PreGenerationError("pre_generation_lease_lost")
        return dict(row)

    def _advance(
        self,
        *,
        run_id: UUID,
        lease_token: UUID,
        stage: str,
        actor: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            owned = self._owned_run_locked(conn, run_id, lease_token)
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET current_stage=%s,stage_attempt=0,status='running',updated_at=now(),
                       last_error_code=NULL,last_error_detail='{}'::jsonb WHERE id=%s""",
                (stage, run_id),
            )
            self._event(
                conn,
                item_id=owned["campaign_item_id"],
                event_type="pre_generation_stage_advanced",
                from_state="auto_progressing",
                to_state="auto_progressing",
                actor=actor,
                details={"next_stage": stage, **details},
            )
        return {"ok": True, "run_id": str(run_id), "stage": stage}

    def _release_waiting(
        self,
        *,
        run_id: UUID,
        lease_token: UUID,
        seconds: int,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._owned_run_locked(conn, run_id, lease_token)
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='waiting',stage_attempt=stage_attempt+1,
                       lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                       next_attempt_at=now()+(%s || ' seconds')::interval,
                       last_error_detail=%s::jsonb,updated_at=now() WHERE id=%s""",
                (seconds, _json(details), run_id),
            )
        return {"ok": True, "waiting": True, "run_id": str(run_id), "retry_in_seconds": seconds, **details}

    def _exception(
        self,
        *,
        run: dict[str, Any],
        lease_token: UUID,
        actor: str,
        code: str,
        category: str,
        severity: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        fingerprint = _sha({"code": code, "category": category, "details": details, "rule_version": RULE_VERSION})
        run_status = "hard_block" if severity == "hard_block" else "human_exception"
        item_state = run_status
        with self.database.transaction() as conn:
            owned = self._owned_run_locked(conn, run["id"], lease_token)
            conn.execute(
                """INSERT INTO football_brief.pre_generation_exceptions
                   (run_id,campaign_item_id,exception_code,category,severity,status,
                    rule_version,fingerprint,details)
                   VALUES (%s,%s,%s,%s,%s,'open',%s,%s,%s::jsonb)
                   ON CONFLICT (run_id,exception_code,fingerprint) DO UPDATE SET
                     status='open',details=EXCLUDED.details,resolved_at=NULL,resolved_by=NULL""",
                (
                    run["id"],
                    owned["campaign_item_id"],
                    code,
                    category,
                    severity,
                    RULE_VERSION,
                    fingerprint,
                    _json(details),
                ),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status=%s,last_error_code=%s,last_error_detail=%s::jsonb,
                       lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,updated_at=now()
                   WHERE id=%s""",
                (run_status, code, _json(details), run["id"]),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state=%s,disposition=%s,updated_at=now() WHERE id=%s""",
                (item_state, run_status, owned["campaign_item_id"]),
            )
            self._event(
                conn,
                item_id=owned["campaign_item_id"],
                event_type=run_status,
                from_state="auto_progressing",
                to_state=item_state,
                actor=actor,
                details={"exception_code": code, "category": category, "severity": severity, **details},
            )
        return {
            "ok": False,
            "terminal": True,
            "run_id": str(run["id"]),
            "status": run_status,
            "exception_code": code,
            "details": details,
        }

    def _system_failure(
        self,
        *,
        run: dict[str, Any],
        lease_token: UUID,
        actor: str,
        code: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return self._exception(
            run=run,
            lease_token=lease_token,
            actor=actor,
            code=code,
            category="system",
            severity="human_exception",
            details=details,
        )

    @staticmethod
    def _check(
        conn: Any,
        *,
        run_id: UUID,
        stage: str,
        key: str,
        status: str,
        score: int | float | Decimal | None,
        evidence: dict[str, Any],
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.pre_generation_checks
               (run_id,stage,check_key,rule_version,status,score,evidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (run_id,stage,check_key,rule_version) DO UPDATE SET
                 status=EXCLUDED.status,score=EXCLUDED.score,evidence=EXCLUDED.evidence,
                 created_at=now()""",
            (run_id, stage, key, RULE_VERSION, status, score, _json(evidence)),
        )

    @staticmethod
    def _event(
        conn: Any,
        *,
        item_id: UUID,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.production_campaign_item_events
               (campaign_item_id,event_type,from_state,to_state,actor,details)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
            (item_id, event_type, from_state, to_state, actor, _json(details)),
        )

    def _approved_fingerprint_count(
        self,
        *,
        brand_id: UUID,
        fingerprint: str,
        current_version_id: UUID,
    ) -> int:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT count(*)::int AS value
                   FROM football_brief.script_versions version
                   JOIN football_brief.script_documents document ON document.id=version.script_document_id
                   JOIN football_brief.portfolio_content content ON content.id=document.portfolio_content_id
                   JOIN football_brief.monthly_content_plans plan ON plan.id=content.plan_id
                   WHERE plan.brand_id=%s AND version.status='approved'
                     AND version.content_fingerprint=%s AND version.id<>%s""",
                (brand_id, fingerprint, current_version_id),
            ).fetchone()
        return int(row["value"] or 0)

    @staticmethod
    def _prohibited_matches(*, text: str, restrictions: dict[str, Any]) -> list[str]:
        terms: list[str] = []
        for key in ("prohibited_terms", "banned_terms", "disallowed_terms", "never_say"):
            raw = restrictions.get(key)
            if isinstance(raw, str):
                terms.extend(part.strip() for part in raw.split(",") if part.strip())
            elif isinstance(raw, list):
                terms.extend(str(part).strip() for part in raw if str(part).strip())
        lowered = text.lower()
        return sorted({term for term in terms if term.lower() in lowered})

    @staticmethod
    def _voice_profile(brand_slug: str) -> dict[str, Any]:
        slug = brand_slug.lower()
        if "hist" in slug:
            return {"voice": "am_adam", "style": "serious documentary", "speed": 0.92}
        if "rawr" in slug or "football" in slug:
            return {"voice": "am_michael", "style": "energetic sports documentary", "speed": 1.0}
        if "ani" in slug:
            return {"voice": "af_sky", "style": "warm cinematic narrator", "speed": 0.96}
        return {"voice": "af_heart", "style": "warm factual narrator", "speed": 0.96}

    @staticmethod
    def _caption(context: dict[str, Any], version: dict[str, Any]) -> str:
        hook = str(version.get("hook_text") or context["title"]).strip()
        return f"{hook}\n\n{context['objective'] or context['topic']}\n\nSave and share if this helped."

    @staticmethod
    def _hashtags(brand_slug: str, title: str) -> list[str]:
        words = [re.sub(r"[^A-Za-z0-9]", "", part) for part in title.split()]
        selected = [f"#{word}" for word in words if len(word) >= 5][:3]
        brand = f"#{re.sub(r'[^A-Za-z0-9]', '', brand_slug.title())}"
        return list(dict.fromkeys([brand, *selected, "#Explained"]))[:5]

    @staticmethod
    def _thumbnail_copy(title: str) -> str:
        words = [word for word in re.split(r"\s+", title.strip()) if word]
        return " ".join(words[:6]).upper()

    @staticmethod
    def _plain(row: dict[str, Any]) -> dict[str, Any]:
        return json.loads(_json(row))

    @staticmethod
    def _require_operator(conn: Any, actor: str) -> None:
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if row is None:
            raise PreGenerationError("operator_inactive_or_missing")


__all__ = ["PreGenerationError", "PreGenerationService", "RULE_VERSION"]
