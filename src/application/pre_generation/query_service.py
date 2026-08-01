from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from src.application.pre_generation.service import PreGenerationError
from src.application.pre_generation.validated_service import ValidatedPreGenerationService


SortKey = Literal[
    "ordinal",
    "priority",
    "scheduled_for",
    "updated_at",
    "title",
    "state",
    "score",
    "exceptions",
]
SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class SortDefinition:
    expression: str
    cast: str
    null_value: Any


SORTS: dict[str, SortDefinition] = {
    "ordinal": SortDefinition("item.ordinal", "integer", 0),
    "priority": SortDefinition("item.priority", "integer", 0),
    "scheduled_for": SortDefinition("item.scheduled_for", "date", "1970-01-01"),
    "updated_at": SortDefinition("item.updated_at", "timestamptz", "1970-01-01T00:00:00+00:00"),
    "title": SortDefinition("lower(item.title)", "text", ""),
    "state": SortDefinition("item.state", "text", ""),
    "score": SortDefinition("COALESCE(run.score,-1)", "numeric", -1),
    "exceptions": SortDefinition(
        "(SELECT count(*) FROM football_brief.pre_generation_exceptions exception_count "
        "WHERE exception_count.campaign_item_id=item.id AND exception_count.status='open')",
        "bigint",
        0,
    ),
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _encode_cursor(*, sort: str, direction: str, value: Any, item_id: Any) -> str:
    payload = json.dumps(
        {"sort": sort, "direction": direction, "value": value, "item_id": str(item_id)},
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, *, sort: str, direction: str) -> dict[str, Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreGenerationError("invalid_campaign_cursor") from exc
    if payload.get("sort") != sort or payload.get("direction") != direction:
        raise PreGenerationError("campaign_cursor_sort_mismatch")
    try:
        UUID(str(payload["item_id"]))
    except (KeyError, ValueError) as exc:
        raise PreGenerationError("invalid_campaign_cursor") from exc
    return payload


def _filters(
    *,
    campaign_id: UUID,
    query: str,
    states: list[str],
    exception_codes: list[str],
) -> tuple[list[str], list[Any]]:
    conditions = ["version.campaign_id=%s"]
    values: list[Any] = [campaign_id]
    if query:
        conditions.append(
            "(item.item_key ILIKE %s OR item.title ILIKE %s OR item.topic ILIKE %s "
            "OR item.objective ILIKE %s OR item.audience ILIKE %s)"
        )
        values.extend([f"%{query}%"] * 5)
    if states:
        conditions.append("item.state=ANY(%s::text[])")
        values.append(states)
    if exception_codes:
        conditions.append(
            "EXISTS (SELECT 1 FROM football_brief.pre_generation_exceptions exception_filter "
            "WHERE exception_filter.campaign_item_id=item.id "
            "AND exception_filter.status='open' "
            "AND exception_filter.exception_code=ANY(%s::text[]))"
        )
        values.append(exception_codes)
    return conditions, values


class CampaignQueryService(ValidatedPreGenerationService):
    def query_items(
        self,
        *,
        campaign_id: UUID,
        query: str | None = None,
        states: list[str] | None = None,
        exception_codes: list[str] | None = None,
        sort: SortKey = "ordinal",
        direction: SortDirection = "asc",
        cursor: str | None = None,
        limit: int = 250,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise PreGenerationError("campaign_query_limit_must_be_1_to_500")
        if sort not in SORTS:
            raise PreGenerationError("unsupported_campaign_sort")
        if direction not in {"asc", "desc"}:
            raise PreGenerationError("unsupported_campaign_sort_direction")
        normalized_states = sorted({value.strip() for value in states or [] if value.strip()})
        normalized_exceptions = sorted(
            {value.strip() for value in exception_codes or [] if value.strip()}
        )
        if len(normalized_states) > 20 or len(normalized_exceptions) > 20:
            raise PreGenerationError("too_many_campaign_filters")
        search = (query or "").strip()
        if len(search) > 500:
            raise PreGenerationError("campaign_query_too_long")

        definition = SORTS[sort]
        sort_expression = f"COALESCE({definition.expression}, %s::{definition.cast})"
        conditions, where_values = _filters(
            campaign_id=campaign_id,
            query=search,
            states=normalized_states,
            exception_codes=normalized_exceptions,
        )
        if cursor:
            decoded = _decode_cursor(cursor, sort=sort, direction=direction)
            operator = ">" if direction == "asc" else "<"
            conditions.append(
                f"({sort_expression},item.id) {operator} (%s::{definition.cast},%s::uuid)"
            )
            where_values.extend([definition.null_value, decoded["value"], decoded["item_id"]])
        order = "ASC" if direction == "asc" else "DESC"
        # Placeholder order follows SQL text: SELECT expression, WHERE values,
        # ORDER BY expression, LIMIT.
        query_values = [
            definition.null_value,
            *where_values,
            definition.null_value,
            limit + 1,
        ]

        with self.database.connection() as conn:
            campaign = conn.execute(
                """SELECT id,name,campaign_key,status,brand_id,updated_at
                   FROM football_brief.production_campaigns WHERE id=%s""",
                (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise PreGenerationError("campaign_not_found")
            rows = conn.execute(
                f"""SELECT item.id,item.item_key,item.ordinal,item.title,item.topic,item.objective,
                            item.audience,item.primary_platform,item.target_platforms,
                            item.target_duration_seconds,item.short_cut_count,item.scheduled_for,
                            item.priority,item.state,item.disposition,item.portfolio_content_id,
                            item.content_family_id,item.updated_at,
                            run.id AS run_id,run.status AS run_status,run.current_stage,run.score,
                            run.correction_count,run.last_error_code,run.next_attempt_at,
                            package.id AS package_id,package.package_sha256,
                            (SELECT count(*) FROM football_brief.pre_generation_exceptions exception_count
                             WHERE exception_count.campaign_item_id=item.id
                               AND exception_count.status='open')::int AS open_exception_count,
                            {sort_expression} AS cursor_sort_value
                     FROM football_brief.production_campaign_items item
                     JOIN football_brief.production_campaign_versions version
                       ON version.id=item.campaign_version_id
                     LEFT JOIN football_brief.pre_generation_runs run
                       ON run.campaign_item_id=item.id
                     LEFT JOIN football_brief.pre_generation_packages package
                       ON package.campaign_item_id=item.id AND package.status='ready'
                     WHERE {' AND '.join(conditions)}
                     ORDER BY {sort_expression} {order},item.id {order}
                     LIMIT %s""",
                tuple(query_values),
            ).fetchall()
            count_conditions, count_values = _filters(
                campaign_id=campaign_id,
                query=search,
                states=normalized_states,
                exception_codes=normalized_exceptions,
            )
            filtered_count = int(
                conn.execute(
                    f"""SELECT count(*)::int AS value
                         FROM football_brief.production_campaign_items item
                         JOIN football_brief.production_campaign_versions version
                           ON version.id=item.campaign_version_id
                         WHERE {' AND '.join(count_conditions)}""",
                    tuple(count_values),
                ).fetchone()["value"]
            )
            state_groups = conn.execute(
                f"""SELECT item.state,count(*)::int AS count
                     FROM football_brief.production_campaign_items item
                     JOIN football_brief.production_campaign_versions version
                       ON version.id=item.campaign_version_id
                     WHERE {' AND '.join(count_conditions)}
                     GROUP BY item.state ORDER BY count(*) DESC,item.state""",
                tuple(count_values),
            ).fetchall()
        has_more = len(rows) > limit
        page = [dict(row) for row in rows[:limit]]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = _encode_cursor(
                sort=sort,
                direction=direction,
                value=last["cursor_sort_value"],
                item_id=last["id"],
            )
        return {
            "ok": True,
            "kind": "campaign_operations_grid",
            "campaign": dict(campaign),
            "items": page,
            "filtered_count": filtered_count,
            "page_count": len(page),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "sort": sort,
            "direction": direction,
            "filters": {
                "query": search or None,
                "states": normalized_states,
                "exception_codes": normalized_exceptions,
            },
            "groups": {str(row["state"]): int(row["count"]) for row in state_groups},
        }

    def retry_matching(
        self,
        *,
        campaign_id: UUID,
        query: str | None,
        states: list[str] | None,
        exception_codes: list[str] | None,
        actor: str,
        maximum: int = 20_000,
    ) -> dict[str, Any]:
        if not 1 <= maximum <= 20_000:
            raise PreGenerationError("bulk_retry_maximum_must_be_1_to_20000")
        normalized_states = sorted({value.strip() for value in states or [] if value.strip()})
        normalized_exceptions = sorted(
            {value.strip() for value in exception_codes or [] if value.strip()}
        )
        search = (query or "").strip()
        conditions, values = _filters(
            campaign_id=campaign_id,
            query=search,
            states=normalized_states,
            exception_codes=normalized_exceptions,
        )
        if not normalized_states:
            conditions.append("item.state IN ('human_exception','hard_block')")
        values.append(maximum + 1)
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            item_rows = conn.execute(
                f"""SELECT item.id,run.id AS run_id
                     FROM football_brief.production_campaign_items item
                     JOIN football_brief.production_campaign_versions version
                       ON version.id=item.campaign_version_id
                     JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                     WHERE {' AND '.join(conditions)}
                     ORDER BY item.ordinal,item.id
                     LIMIT %s FOR UPDATE OF item,run SKIP LOCKED""",
                tuple(values),
            ).fetchall()
            if len(item_rows) > maximum:
                raise PreGenerationError(
                    "bulk_retry_selection_exceeds_maximum",
                    details={"maximum": maximum},
                )
            if not item_rows:
                raise PreGenerationError("bulk_retry_selection_empty")
            item_ids = [row["id"] for row in item_rows]
            run_ids = [row["run_id"] for row in item_rows]
            action = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,succeeded_count,
                    failed_count,result,requested_by,started_at,completed_at)
                   VALUES (%s,'retry','completed',%s::jsonb,%s,%s,0,%s::jsonb,
                           %s,now(),now()) RETURNING *""",
                (
                    campaign_id,
                    _json(
                        {
                            "query": search or None,
                            "states": normalized_states,
                            "exception_codes": normalized_exceptions,
                            "item_ids": [str(value) for value in item_ids],
                        }
                    ),
                    len(item_ids),
                    len(item_ids),
                    _json({"operation": "retry_matching"}),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                       next_attempt_at=now(),last_error_code=NULL,last_error_detail='{}'::jsonb,
                       updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (run_ids,),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='auto_progressing',disposition=NULL,updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (item_ids,),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_exceptions
                   SET status='superseded',resolved_at=now(),resolved_by=%s,
                       resolution=jsonb_build_object('action','bulk_retry_matching')
                   WHERE campaign_item_id=ANY(%s::uuid[]) AND status='open'""",
                (actor, item_ids),
            )
        return {
            "ok": True,
            "kind": "campaign_bulk_retry_matching",
            "count": len(item_ids),
            "action_id": str(action["id"]),
        }


__all__ = [
    "CampaignQueryService",
    "SORTS",
    "SortDirection",
    "SortKey",
]
