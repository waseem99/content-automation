from __future__ import annotations

import json
import os

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


PROVIDER_WORKERS = (
    ("FAL_WORKER_OPERATOR_ID", "fal-worker", "fal Managed Renderer"),
    ("VIDU_WORKER_OPERATOR_ID", "vidu-worker", "Vidu Managed Renderer"),
)


def onboard_provider_workers(database: Database, *, actor: str = "local-super-admin") -> dict:
    workers: list[dict] = []
    with database.transaction() as conn:
        admin = conn.execute(
            "SELECT 1 FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (actor,),
        ).fetchone()
        if not admin:
            fallback = conn.execute(
                """SELECT operator_id FROM football_brief.operator_users
                   WHERE active=true ORDER BY created_at LIMIT 1"""
            ).fetchone()
            if not fallback:
                raise RuntimeError("an active operator is required before provider worker onboarding")
            actor = str(fallback["operator_id"])
        brands = conn.execute(
            "SELECT id FROM football_brief.brands WHERE active=true ORDER BY id"
        ).fetchall()
        for env_name, default_id, display_name in PROVIDER_WORKERS:
            worker_id = os.getenv(env_name, default_id)
            worker = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id,display_name,active,created_by)
                   VALUES (%s,%s,true,%s)
                   ON CONFLICT (operator_id) DO UPDATE SET
                     display_name=EXCLUDED.display_name,active=true
                   RETURNING *""",
                (worker_id, display_name, actor),
            ).fetchone()
            conn.execute(
                "DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s",
                (worker["id"],),
            )
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id,role,assigned_by) VALUES (%s,'producer',%s)""",
                (worker["id"], actor),
            )
            conn.execute(
                "DELETE FROM football_brief.operator_brand_assignments WHERE operator_user_id=%s",
                (worker["id"],),
            )
            for brand in brands:
                conn.execute(
                    """INSERT INTO football_brief.operator_brand_assignments
                       (operator_user_id,brand_id,assigned_by)
                       VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (worker["id"], brand["id"], actor),
                )
            workers.append(
                {
                    "operator_id": worker_id,
                    "display_name": display_name,
                    "internal_roles": ["producer"],
                    "api_key_created": False,
                    "can_approve": False,
                    "can_publish": False,
                }
            )
    return {"ok": True, "workers": workers}


def main() -> int:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        result = onboard_provider_workers(database)
    finally:
        database.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
