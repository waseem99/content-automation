from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any
from uuid import UUID

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import EvidenceCategory
from src.application.acceptance.service import CONTENT_CATEGORIES


REQUIRED_BRAND_SLUGS = ("animal-x", "rawr-nation")
PRODUCTION_MODES = ("local_only", "managed_render")
SELECTION_CATEGORIES = (
    EvidenceCategory.BRAND_PROFILE,
    EvidenceCategory.NARRATION_PRESET,
    EvidenceCategory.ROLE_ASSIGNMENT,
    EvidenceCategory.CONCEPT_APPROVAL,
    EvidenceCategory.SCRIPT_APPROVAL,
    EvidenceCategory.SOURCE_EVIDENCE,
)
BOUNDING_PILOT_STATUSES = {"draft", "running", "blocked", "accepted"}


class AcceptanceCandidateError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _public_value(value: Any) -> Any:
    if isinstance(value, (UUID, date, datetime)):
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)
    return value


class AcceptanceCandidateService:
    """Read-only inventory of canonical P100 content candidates."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self.acceptance = AcceptancePilotService(database)

    def inventory(self, *, limit_per_brand: int = 50) -> dict[str, Any]:
        if limit_per_brand < 1 or limit_per_brand > 100:
            raise AcceptanceCandidateError(
                "candidate_limit_out_of_range",
                details={"minimum": 1, "maximum": 100},
            )
        with self.database.connection() as conn:
            brands = conn.execute(
                """SELECT id,slug,display_name
                   FROM football_brief.brands
                   WHERE slug=ANY(%s::text[])
                   ORDER BY slug""",
                (list(REQUIRED_BRAND_SLUGS),),
            ).fetchall()
            found_slugs = {row["slug"] for row in brands}
            missing = sorted(set(REQUIRED_BRAND_SLUGS) - found_slugs)
            if missing:
                raise AcceptanceCandidateError(
                    "required_pilot_brands_missing",
                    details={"missing_brand_slugs": missing},
                )

            contents = conn.execute(
                """WITH ranked AS (
                       SELECT pc.id AS portfolio_content_id,
                              pc.version AS content_version,
                              pc.title,
                              pc.scheduled_for,
                              pc.brand_profile_id,
                              pc.narration_preset_id,
                              b.id AS brand_id,
                              b.slug AS brand_slug,
                              b.display_name AS brand_name,
                              row_number() OVER (
                                  PARTITION BY b.id
                                  ORDER BY pc.scheduled_for DESC,pc.title,pc.id
                              ) AS brand_rank
                       FROM football_brief.portfolio_content pc
                       JOIN football_brief.monthly_content_plans mcp ON mcp.id=pc.plan_id
                       JOIN football_brief.brands b ON b.id=mcp.brand_id
                       WHERE b.slug=ANY(%s::text[])
                   )
                   SELECT * FROM ranked
                   WHERE brand_rank<=%s
                   ORDER BY brand_slug,scheduled_for DESC,title,portfolio_content_id""",
                (list(REQUIRED_BRAND_SLUGS), limit_per_brand),
            ).fetchall()

            reports: list[dict[str, Any]] = []
            for content in contents:
                bindings = conn.execute(
                    """SELECT ap.id AS pilot_id,ap.pilot_key,ap.version AS pilot_version,
                              ap.status,api.production_mode,api.status AS item_status
                       FROM football_brief.acceptance_pilot_items api
                       JOIN football_brief.acceptance_pilots ap ON ap.id=api.pilot_id
                       WHERE api.portfolio_content_id=%s AND api.content_version=%s
                       ORDER BY ap.created_at,ap.id""",
                    (content["portfolio_content_id"], content["content_version"]),
                ).fetchall()
                active_or_accepted = any(
                    row["status"] in BOUNDING_PILOT_STATUSES for row in bindings
                )
                mode_reports: dict[str, Any] = {}
                for mode in PRODUCTION_MODES:
                    context = {
                        "portfolio_content_id": content["portfolio_content_id"],
                        "content_version": content["content_version"],
                        "brand_id": content["brand_id"],
                        "production_mode": mode,
                    }
                    checks = self.acceptance._system_checks(conn, context)
                    categories = [
                        {
                            "category": category.value,
                            "passed": bool(checks[category]["passed"]),
                            "subject_type": checks[category]["subject_type"],
                            "subject_id": checks[category]["subject_id"],
                            "subject_version": checks[category].get("subject_version"),
                        }
                        for category in CONTENT_CATEGORIES
                    ]
                    passed_by_category = {
                        entry["category"]: entry["passed"] for entry in categories
                    }
                    selection_blockers = [
                        category.value
                        for category in SELECTION_CATEGORIES
                        if not passed_by_category[category.value]
                    ]
                    completion_blockers = [
                        category.value
                        for category in CONTENT_CATEGORIES
                        if not passed_by_category[category.value]
                    ]
                    if active_or_accepted:
                        selection_blockers.append("already_bound_to_active_or_accepted_pilot")
                        completion_blockers.append("already_bound_to_active_or_accepted_pilot")
                    mode_blockers = []
                    if mode == "local_only" and not passed_by_category[
                        EvidenceCategory.SPEND_APPROVAL.value
                    ]:
                        mode_blockers.append("zero_cost_local_routing_not_complete")
                    if mode == "managed_render":
                        if not passed_by_category[EvidenceCategory.SPEND_APPROVAL.value]:
                            mode_blockers.append("managed_spend_reconciliation_not_complete")
                        if not passed_by_category[EvidenceCategory.RENDERER_LINEAGE.value]:
                            mode_blockers.append("managed_renderer_lineage_not_complete")
                    selection_ready = not selection_blockers
                    production_ready = not completion_blockers
                    mode_reports[mode] = {
                        "selection_ready": selection_ready,
                        "production_complete": production_ready,
                        "selection_passed_count": len(SELECTION_CATEGORIES) - len(
                            [value for value in selection_blockers if value in {c.value for c in SELECTION_CATEGORIES}]
                        ),
                        "canonical_passed_count": sum(
                            1 for entry in categories if entry["passed"]
                        ),
                        "canonical_required_count": len(CONTENT_CATEGORIES),
                        "selection_blockers": selection_blockers,
                        "completion_blockers": completion_blockers,
                        "mode_blockers": mode_blockers,
                        "categories": categories,
                    }

                reports.append(
                    {
                        "portfolio_content_id": str(content["portfolio_content_id"]),
                        "content_version": int(content["content_version"]),
                        "brand_id": str(content["brand_id"]),
                        "brand_slug": content["brand_slug"],
                        "brand_name": content["brand_name"],
                        "title": content["title"],
                        "scheduled_for": _public_value(content["scheduled_for"]),
                        "brand_profile_id": (
                            str(content["brand_profile_id"])
                            if content["brand_profile_id"]
                            else None
                        ),
                        "narration_preset_id": (
                            str(content["narration_preset_id"])
                            if content["narration_preset_id"]
                            else None
                        ),
                        "already_bound_to_active_or_accepted_pilot": active_or_accepted,
                        "pilot_bindings": [
                            {
                                "pilot_id": str(row["pilot_id"]),
                                "pilot_key": row["pilot_key"],
                                "pilot_version": int(row["pilot_version"]),
                                "pilot_status": row["status"],
                                "production_mode": row["production_mode"],
                                "item_status": row["item_status"],
                            }
                            for row in bindings
                        ],
                        "modes": mode_reports,
                    }
                )

        for mode in PRODUCTION_MODES:
            ranked = sorted(
                reports,
                key=lambda report: (
                    report["brand_slug"],
                    -int(report["modes"][mode]["production_complete"]),
                    -report["modes"][mode]["canonical_passed_count"],
                    -int(report["modes"][mode]["selection_ready"]),
                    -report["modes"][mode]["selection_passed_count"],
                    report["scheduled_for"] or "",
                    report["portfolio_content_id"],
                ),
            )
            positions: dict[str, int] = defaultdict(int)
            for report in ranked:
                positions[report["brand_slug"]] += 1
                report["modes"][mode]["rank_within_brand"] = positions[
                    report["brand_slug"]
                ]

        summaries: dict[str, Any] = {}
        ready_to_select_four = True
        for brand in brands:
            brand_reports = [
                report for report in reports if report["brand_slug"] == brand["slug"]
            ]
            local_ids = {
                report["portfolio_content_id"]
                for report in brand_reports
                if report["modes"]["local_only"]["production_complete"]
            }
            managed_ids = {
                report["portfolio_content_id"]
                for report in brand_reports
                if report["modes"]["managed_render"]["production_complete"]
            }
            distinct_ready_pair = any(
                local_id != managed_id
                for local_id in local_ids
                for managed_id in managed_ids
            )
            ready_to_select_four = ready_to_select_four and distinct_ready_pair
            summaries[brand["slug"]] = {
                "brand_id": str(brand["id"]),
                "brand_name": brand["display_name"],
                "candidate_count": len(brand_reports),
                "selection_ready_local_count": sum(
                    1
                    for report in brand_reports
                    if report["modes"]["local_only"]["selection_ready"]
                ),
                "selection_ready_managed_count": sum(
                    1
                    for report in brand_reports
                    if report["modes"]["managed_render"]["selection_ready"]
                ),
                "production_complete_local_count": len(local_ids),
                "production_complete_managed_count": len(managed_ids),
                "distinct_production_complete_pair": distinct_ready_pair,
            }

        return {
            "ok": True,
            "kind": "p100_pilot_candidate_inventory",
            "required_brand_slugs": list(REQUIRED_BRAND_SLUGS),
            "limit_per_brand": limit_per_brand,
            "ready_to_select_four_production_complete_items": ready_to_select_four,
            "brands": summaries,
            "candidates": reports,
        }


__all__ = [
    "AcceptanceCandidateError",
    "AcceptanceCandidateService",
    "PRODUCTION_MODES",
    "REQUIRED_BRAND_SLUGS",
    "SELECTION_CATEGORIES",
]
