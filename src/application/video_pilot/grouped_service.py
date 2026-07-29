from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.video_pilot.models import PilotCaseCreateRequest, PilotItemCreateRequest
from src.application.video_pilot.service import VideoPilotError, VideoPilotService


class GroupedVideoPilotService(VideoPilotService):
    def create_item(self, run_id: UUID, request: PilotItemCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            run = conn.execute(
                "SELECT id,status FROM football_brief.video_pilot_runs WHERE id=%s FOR SHARE",
                (run_id,),
            ).fetchone()
            if not run:
                raise VideoPilotError("pilot_run_not_found")
            if run["status"] not in {"planned", "running"}:
                raise VideoPilotError("pilot_run_not_editable", details={"status": run["status"]})
            if request.portfolio_content_id and not conn.execute(
                "SELECT id FROM football_brief.portfolio_content WHERE id=%s",
                (request.portfolio_content_id,),
            ).fetchone():
                raise VideoPilotError("portfolio_content_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.video_pilot_items WHERE pilot_run_id=%s AND item_key=%s",
                (run_id, request.item_key),
            ).fetchone()
            if existing:
                raise VideoPilotError("pilot_item_key_exists", details={"pilot_item_id": str(existing["id"])})
            item = conn.execute(
                """INSERT INTO football_brief.video_pilot_items
                   (pilot_run_id,item_key,title,portfolio_content_id,target_duration_seconds,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,'planned',%s) RETURNING *""",
                (
                    run_id,
                    request.item_key,
                    request.title.strip(),
                    request.portfolio_content_id,
                    request.target_duration_seconds,
                    actor,
                ),
            ).fetchone()
        return {"ok": True, "kind": "video_pilot_item_created", "item": dict(item)}

    def create_case(self, run_id: UUID, request: PilotCaseCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            run = conn.execute(
                "SELECT id,status FROM football_brief.video_pilot_runs WHERE id=%s FOR SHARE",
                (run_id,),
            ).fetchone()
            if not run:
                raise VideoPilotError("pilot_run_not_found")
            if run["status"] not in {"planned", "running"}:
                raise VideoPilotError("pilot_run_not_editable", details={"status": run["status"]})
            item = conn.execute(
                "SELECT id,status FROM football_brief.video_pilot_items WHERE id=%s AND pilot_run_id=%s FOR UPDATE",
                (request.pilot_item_id, run_id),
            ).fetchone()
            if not item:
                raise VideoPilotError("pilot_item_not_found")
            if item["status"] in {"completed", "cancelled"}:
                raise VideoPilotError("pilot_item_not_editable", details={"status": item["status"]})
            if request.input_asset_id and not conn.execute(
                "SELECT id FROM football_brief.assets WHERE id=%s", (request.input_asset_id,)
            ).fetchone():
                raise VideoPilotError("pilot_input_asset_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.video_pilot_cases WHERE pilot_run_id=%s AND case_key=%s",
                (run_id, request.case_key),
            ).fetchone()
            if existing:
                raise VideoPilotError("pilot_case_key_exists", details={"pilot_case_id": str(existing["id"])})
            case = conn.execute(
                """INSERT INTO football_brief.video_pilot_cases
                   (pilot_run_id,pilot_item_id,case_key,title,shot_class,difficulty,distribution_scope,
                    release_territories,target_duration_seconds,prompt,negative_prompt,input_asset_id,
                    required_model_keys,acceptance_criteria,status,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::text[],%s,%s,%s,%s,%s::text[],%s::jsonb,'ready',%s)
                   RETURNING *""",
                (
                    run_id,
                    request.pilot_item_id,
                    request.case_key,
                    request.title.strip(),
                    request.shot_class.value,
                    request.difficulty.value,
                    request.distribution_scope.value,
                    list(request.release_territories),
                    request.target_duration_seconds,
                    request.prompt.strip(),
                    request.negative_prompt.strip() if request.negative_prompt else None,
                    request.input_asset_id,
                    list(request.required_model_keys),
                    self._json_value(request.acceptance_criteria),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE football_brief.video_pilot_items SET status='production' WHERE id=%s AND status='planned'",
                (request.pilot_item_id,),
            )
        return {"ok": True, "kind": "video_pilot_case_created", "case": dict(case)}

    def review_attempt(self, attempt_id: UUID, request: Any, *, actor: str) -> dict[str, Any]:
        result = super().review_attempt(attempt_id, request, actor=actor)
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT c.pilot_item_id FROM football_brief.video_pilot_attempts a
                   JOIN football_brief.video_pilot_cases c ON c.id=a.pilot_case_id
                   WHERE a.id=%s""",
                (attempt_id,),
            ).fetchone()
            if row:
                remaining = int(
                    conn.execute(
                        """SELECT count(*)::int AS value FROM football_brief.video_pilot_cases
                           WHERE pilot_item_id=%s AND status NOT IN ('completed','cancelled')""",
                        (row["pilot_item_id"],),
                    ).fetchone()["value"]
                )
                total = int(
                    conn.execute(
                        "SELECT count(*)::int AS value FROM football_brief.video_pilot_cases WHERE pilot_item_id=%s",
                        (row["pilot_item_id"],),
                    ).fetchone()["value"]
                )
                if total > 0 and remaining == 0:
                    conn.execute(
                        "UPDATE football_brief.video_pilot_items SET status='completed' WHERE id=%s",
                        (row["pilot_item_id"],),
                    )
                else:
                    conn.execute(
                        "UPDATE football_brief.video_pilot_items SET status='production' WHERE id=%s AND status<>'cancelled'",
                        (row["pilot_item_id"],),
                    )
        return result

    def detail(self, run_id: UUID) -> dict[str, Any]:
        detail = super().detail(run_id)
        with self.database.connection() as conn:
            items = conn.execute(
                "SELECT * FROM football_brief.video_pilot_items WHERE pilot_run_id=%s ORDER BY item_key,id",
                (run_id,),
            ).fetchall()
        detail["items"] = [dict(row) for row in items]
        return detail

    @staticmethod
    def _json_value(value: Any) -> str:
        import json

        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
