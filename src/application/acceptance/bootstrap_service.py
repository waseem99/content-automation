from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.acceptance.bootstrap_models import PilotBootstrapRequest
from src.application.acceptance.candidate_service import (
    BOUNDING_PILOT_STATUSES,
    REQUIRED_BRAND_SLUGS,
    SELECTION_CATEGORIES,
)
from src.application.acceptance.service import AcceptancePilotError, _digest, _json
from src.application.acceptance.validated_service import (
    P100_RUNBOOK_RELATIVE_PATH,
    ValidatedAcceptancePilotService,
    p100_runbook_sha256,
)


_EXPECTED_BRAND_MODES = {
    (brand_slug, production_mode)
    for brand_slug in REQUIRED_BRAND_SLUGS
    for production_mode in ("local_only", "managed_render")
}


class AcceptanceBootstrapService(ValidatedAcceptancePilotService):
    """Atomically create or replay one bounded draft P100 pilot."""

    def bootstrap(
        self,
        request: PilotBootstrapRequest,
        *,
        actor: str,
    ) -> dict[str, Any]:
        runbook_sha256 = p100_runbook_sha256()
        request_fingerprint = _digest(request.canonical_payload())
        reused = False

        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (request.pilot_key,),
            )
            current = conn.execute(
                """SELECT * FROM football_brief.acceptance_pilots
                   WHERE pilot_key=%s ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (request.pilot_key,),
            ).fetchone()

            if current and current["status"] in {"draft", "running", "blocked"}:
                stored_fingerprint = (current["acceptance_policy"] or {}).get(
                    "bootstrap_request_sha256"
                )
                if current["status"] != "draft" or stored_fingerprint != request_fingerprint:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_key_conflict",
                        details={
                            "pilot_id": str(current["id"]),
                            "pilot_status": current["status"],
                            "stored_request_sha256": stored_fingerprint,
                            "requested_sha256": request_fingerprint,
                        },
                    )
                existing_items = self._pilot_items(conn, pilot_id=current["id"])
                if self._canonical_existing_items(existing_items) != self._canonical_request_items(
                    request
                ):
                    raise AcceptancePilotError(
                        "pilot_bootstrap_replay_mismatch",
                        details={
                            "pilot_id": str(current["id"]),
                            "requested_sha256": request_fingerprint,
                        },
                    )
                pilot = current
                items = existing_items
                reused = True
            else:
                requested_ids = [item.portfolio_content_id for item in request.items]
                content_rows = conn.execute(
                    """SELECT pc.id AS portfolio_content_id,pc.version AS content_version,
                              mp.brand_id,b.slug AS brand_slug,b.display_name AS brand_name
                       FROM football_brief.portfolio_content pc
                       JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                       JOIN football_brief.brands b ON b.id=mp.brand_id
                       WHERE pc.id=ANY(%s::uuid[])
                       ORDER BY b.slug,pc.id
                       FOR SHARE OF pc""",
                    (requested_ids,),
                ).fetchall()
                rows_by_id = {row["portfolio_content_id"]: row for row in content_rows}
                missing = sorted(
                    str(content_id)
                    for content_id in requested_ids
                    if content_id not in rows_by_id
                )
                if missing:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_content_not_found",
                        details={"portfolio_content_ids": missing},
                    )

                requested_by_id = {
                    item.portfolio_content_id: item for item in request.items
                }
                stale: list[dict[str, Any]] = []
                brand_modes: set[tuple[str, str]] = set()
                for content_id, item in requested_by_id.items():
                    row = rows_by_id[content_id]
                    if int(row["content_version"]) != item.content_version:
                        stale.append(
                            {
                                "portfolio_content_id": str(content_id),
                                "requested_version": item.content_version,
                                "current_version": int(row["content_version"]),
                            }
                        )
                    brand_modes.add((row["brand_slug"], item.production_mode.value))
                if stale:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_stale_content_version",
                        details={"items": stale},
                    )
                if brand_modes != _EXPECTED_BRAND_MODES:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_scope_mismatch",
                        details={
                            "required_brand_modes": [
                                {"brand_slug": brand, "production_mode": mode}
                                for brand, mode in sorted(_EXPECTED_BRAND_MODES)
                            ],
                            "provided_brand_modes": [
                                {"brand_slug": brand, "production_mode": mode}
                                for brand, mode in sorted(brand_modes)
                            ],
                        },
                    )

                bindings = conn.execute(
                    """SELECT api.portfolio_content_id,api.content_version,
                              ap.id AS pilot_id,ap.pilot_key,ap.version AS pilot_version,
                              ap.status AS pilot_status
                       FROM football_brief.acceptance_pilot_items api
                       JOIN football_brief.acceptance_pilots ap ON ap.id=api.pilot_id
                       WHERE api.portfolio_content_id=ANY(%s::uuid[])
                         AND ap.status=ANY(%s::text[])
                       ORDER BY ap.created_at,ap.id""",
                    (requested_ids, sorted(BOUNDING_PILOT_STATUSES)),
                ).fetchall()
                conflicts = [
                    {
                        "portfolio_content_id": str(row["portfolio_content_id"]),
                        "content_version": int(row["content_version"]),
                        "pilot_id": str(row["pilot_id"]),
                        "pilot_key": row["pilot_key"],
                        "pilot_version": int(row["pilot_version"]),
                        "pilot_status": row["pilot_status"],
                    }
                    for row in bindings
                    if requested_by_id[row["portfolio_content_id"]].content_version
                    == int(row["content_version"])
                ]
                if conflicts:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_content_already_bound",
                        details={"bindings": conflicts},
                    )

                candidate_failures: list[dict[str, Any]] = []
                for content_id, item in requested_by_id.items():
                    row = rows_by_id[content_id]
                    checks = self._system_checks(
                        conn,
                        {
                            "portfolio_content_id": content_id,
                            "content_version": item.content_version,
                            "brand_id": row["brand_id"],
                            "production_mode": item.production_mode.value,
                        },
                    )
                    blockers = [
                        category.value
                        for category in SELECTION_CATEGORIES
                        if not checks[category]["passed"]
                    ]
                    if blockers:
                        candidate_failures.append(
                            {
                                "portfolio_content_id": str(content_id),
                                "content_version": item.content_version,
                                "brand_slug": row["brand_slug"],
                                "production_mode": item.production_mode.value,
                                "selection_blockers": blockers,
                            }
                        )
                if candidate_failures:
                    raise AcceptancePilotError(
                        "pilot_bootstrap_candidate_not_selectable",
                        details={"items": candidate_failures},
                    )

                version = int(current["version"]) + 1 if current else 1
                parent_pilot_id = current["id"] if current else None
                acceptance_policy = {
                    **request.acceptance_policy,
                    "bootstrap_kind": "controlled_draft",
                    "bootstrap_item_count": 4,
                    "bootstrap_request_sha256": request_fingerprint,
                }
                pilot = conn.execute(
                    """INSERT INTO football_brief.acceptance_pilots
                       (pilot_key,version,parent_pilot_id,scope,acceptance_policy,created_by)
                       VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING *""",
                    (
                        request.pilot_key,
                        version,
                        parent_pilot_id,
                        _json(
                            {
                                "brand_slugs": list(REQUIRED_BRAND_SLUGS),
                                "items_per_brand": 2,
                                "total_items": 4,
                                "required_modes": ["local_only", "managed_render"],
                                "staging_delivery": "simulated_only",
                                "live_delivery": "external_evidence_after_signoff",
                            }
                        ),
                        _json(acceptance_policy),
                        actor,
                    ),
                ).fetchone()
                self._event(
                    conn,
                    pilot["id"],
                    None,
                    "pilot_created",
                    actor,
                    {
                        "version": version,
                        "bootstrap_request_sha256": request_fingerprint,
                    },
                )

                items = []
                ordered_items = sorted(
                    request.items,
                    key=lambda item: (
                        rows_by_id[item.portfolio_content_id]["brand_slug"],
                        item.production_mode.value,
                        str(item.portfolio_content_id),
                    ),
                )
                for item in ordered_items:
                    content = rows_by_id[item.portfolio_content_id]
                    row = conn.execute(
                        """INSERT INTO football_brief.acceptance_pilot_items
                           (pilot_id,brand_id,portfolio_content_id,content_version,
                            production_mode,required_revision_stages,
                            live_delivery_evidence_required,created_by)
                           VALUES (%s,%s,%s,%s,%s,ARRAY['script','narration','visual']::text[],%s,%s)
                           RETURNING *""",
                        (
                            pilot["id"],
                            content["brand_id"],
                            item.portfolio_content_id,
                            item.content_version,
                            item.production_mode.value,
                            item.live_delivery_evidence_required,
                            actor,
                        ),
                    ).fetchone()
                    items.append(row)
                    self._event(
                        conn,
                        pilot["id"],
                        row["id"],
                        "item_added",
                        actor,
                        {
                            "brand_slug": content["brand_slug"],
                            "production_mode": item.production_mode.value,
                            "bootstrap_request_sha256": request_fingerprint,
                        },
                    )

        readiness = self.readiness(pilot_id=pilot["id"])
        return {
            "ok": True,
            "kind": "p100_controlled_draft_bootstrap",
            "reused": reused,
            "bootstrap_request_sha256": request_fingerprint,
            "pilot": dict(pilot),
            "items": [dict(item) for item in items],
            "readiness": readiness,
            "runbook": {
                "path": P100_RUNBOOK_RELATIVE_PATH,
                "sha256": runbook_sha256,
            },
        }

    @staticmethod
    def _pilot_items(conn: Any, *, pilot_id: UUID) -> list[Any]:
        return list(
            conn.execute(
                """SELECT api.*,b.slug AS brand_slug
                   FROM football_brief.acceptance_pilot_items api
                   JOIN football_brief.brands b ON b.id=api.brand_id
                   WHERE api.pilot_id=%s
                   ORDER BY b.slug,api.production_mode,api.portfolio_content_id""",
                (pilot_id,),
            ).fetchall()
        )

    @staticmethod
    def _canonical_existing_items(items: list[Any]) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "portfolio_content_id": str(item["portfolio_content_id"]),
                    "content_version": int(item["content_version"]),
                    "production_mode": item["production_mode"],
                    "live_delivery_evidence_required": bool(
                        item["live_delivery_evidence_required"]
                    ),
                }
                for item in items
            ],
            key=lambda item: (
                item["portfolio_content_id"],
                item["content_version"],
                item["production_mode"],
            ),
        )

    @staticmethod
    def _canonical_request_items(request: PilotBootstrapRequest) -> list[dict[str, Any]]:
        return sorted(
            [item.model_dump(mode="json") for item in request.items],
            key=lambda item: (
                item["portfolio_content_id"],
                item["content_version"],
                item["production_mode"],
            ),
        )


__all__ = ["AcceptanceBootstrapService"]
