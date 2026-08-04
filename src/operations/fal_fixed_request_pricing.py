from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.renderers.models import RendererRepriceRequest
from src.application.renderers.validated_service import ValidatedRendererCatalogueService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings

TARGET_PROVIDER = "fal"
TARGET_MODEL = "fal-ai/wan/v2.2-5b/image-to-video"
TARGET_OPERATION = "image_to_video"


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _actor(conn: Any) -> str:
    for operator_id in ("local-super-admin", "local-admin"):
        row = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if row:
            return str(row["operator_id"])
    row = conn.execute(
        """SELECT operator_id FROM football_brief.operator_users
           WHERE active=true ORDER BY created_at,id LIMIT 1"""
    ).fetchone()
    if not row:
        raise RuntimeError("an active operator is required for fal pricing migration")
    return str(row["operator_id"])


def migrate_fal_fixed_request_pricing(database: Database) -> dict[str, Any]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT * FROM football_brief.renderer_catalogue_entries
               WHERE provider_key=%s AND model_key=%s AND operation=%s AND status='active'
               ORDER BY version DESC LIMIT 1""",
            (TARGET_PROVIDER, TARGET_MODEL, TARGET_OPERATION),
        ).fetchone()
        if row is None:
            return {
                "ok": True,
                "kind": "fal_fixed_request_pricing_migration",
                "status": "not_configured",
                "changed": False,
            }
        actor = _actor(conn)
        entry = dict(row)

    pricing = dict(entry.get("pricing") or {})
    fixed_request = _decimal(pricing.get("per_request_usd"))
    if fixed_request > 0:
        return {
            "ok": True,
            "kind": "fal_fixed_request_pricing_migration",
            "status": "already_fixed_request",
            "changed": False,
            "entry_id": str(entry["id"]),
        }

    legacy_value = _decimal(pricing.get("per_second_usd"))
    if legacy_value <= 0:
        legacy_value = _decimal(pricing.get("base_usd"))
    if legacy_value <= 0:
        raise RuntimeError(
            "active fal Wan pricing has no reviewed positive fixed charge; rerun provider setup with "
            "-FalPricePerRequestUsd before enabling paid execution"
        )

    upgraded = {
        key: value
        for key, value in pricing.items()
        if key not in {"per_second_usd", "base_usd", "per_request_usd"}
    }
    upgraded["per_request_usd"] = legacy_value
    service = ValidatedRendererCatalogueService(database)
    result = service.reprice(
        entry_id=UUID(str(entry["id"])),
        request=RendererRepriceRequest(
            pricing=upgraded,
            rationale=(
                "Correct fal Wan 2.2 billing from the legacy duration field to the reviewed "
                "fixed request charge. No provider request is submitted."
            ),
            activate=True,
        ),
        actor=actor,
    )
    return {
        "ok": True,
        "kind": "fal_fixed_request_pricing_migration",
        "status": "migrated",
        "changed": True,
        "previous_entry_id": str(entry["id"]),
        "entry_id": str(result["entry"]["id"]),
    }


def main() -> int:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        result = migrate_fal_fixed_request_pricing(database)
    finally:
        database.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
