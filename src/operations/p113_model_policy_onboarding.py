from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


POLICIES: tuple[dict[str, Any], ...] = (
    {
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "model_display_name": "Wan2.2 TI2V-5B",
        "license_name": "Apache License 2.0",
        "license_spdx": "Apache-2.0",
        "terms_url": "https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt",
        "commercial_use_allowed": True,
        "allowed_use_scopes": ["internal", "territory_limited", "global_public"],
        "allowed_territories": ["worldwide"],
        "prohibited_territories": [],
        "requires_written_clearance": False,
        "evidence": (
            "Official Wan2.2 repository identifies TI2V-5B and Apache-2.0 licensing; "
            "release preflight still requires content, asset, and applicable-law review."
        ),
        "metadata": {
            "source_kind": "official_repository",
            "global_public_default_candidate": True,
            "legal_review_is_not_replaced": True,
        },
    },
    {
        "provider_key": "tencent-hunyuan",
        "model_key": "HunyuanVideo-1.5-480p-I2V-Step-Distilled",
        "model_display_name": "HunyuanVideo 1.5 480p I2V Step-Distilled",
        "license_name": "Tencent Hunyuan Community License Agreement",
        "license_spdx": None,
        "terms_url": "https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE",
        "commercial_use_allowed": True,
        "allowed_use_scopes": ["internal", "territory_limited"],
        "allowed_territories": ["worldwide_except_european_union_united_kingdom_south_korea"],
        "prohibited_territories": ["European Union", "United Kingdom", "South Korea"],
        "requires_written_clearance": True,
        "evidence": (
            "Official license limits use, display and distribution of model outputs to the Territory, "
            "defined as worldwide excluding the European Union, United Kingdom and South Korea; "
            "global public release is rejected without written clearance."
        ),
        "metadata": {
            "source_kind": "official_model_license",
            "global_public_default_candidate": False,
            "territory_restriction_enforced": True,
            "legal_review_is_not_replaced": True,
        },
    },
)


def _canonical_evidence(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_key": policy["provider_key"],
        "model_key": policy["model_key"],
        "license_name": policy["license_name"],
        "terms_url": policy["terms_url"],
        "commercial_use_allowed": policy["commercial_use_allowed"],
        "allowed_use_scopes": policy["allowed_use_scopes"],
        "allowed_territories": policy["allowed_territories"],
        "prohibited_territories": policy["prohibited_territories"],
        "requires_written_clearance": policy["requires_written_clearance"],
        "evidence": policy["evidence"],
    }


def _digest(policy: dict[str, Any]) -> str:
    payload = json.dumps(_canonical_evidence(policy), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def onboard() -> dict[str, Any]:
    actor = os.getenv("LOCAL_SUPER_ADMIN_OPERATOR_ID", "local-super-admin")
    database = Database(get_database_settings())
    database.open(require_schema=True)
    results: list[dict[str, Any]] = []
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            if not operator:
                raise RuntimeError("P113 model policy onboarding requires the active local Super Admin operator")

            for policy in POLICIES:
                evidence_digest = _digest(policy)
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"video-model-policy:{policy['provider_key']}:{policy['model_key']}",),
                )
                active = conn.execute(
                    """SELECT * FROM football_brief.video_model_use_policies
                       WHERE provider_key=%s AND model_key=%s AND status='active'
                       ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                    (policy["provider_key"], policy["model_key"]),
                ).fetchone()
                if active and str(active["evidence_digest"]) == evidence_digest:
                    results.append(
                        {
                            "provider_key": policy["provider_key"],
                            "model_key": policy["model_key"],
                            "policy_id": str(active["id"]),
                            "version": int(active["version"]),
                            "reused": True,
                        }
                    )
                    continue

                version = int(
                    conn.execute(
                        """SELECT COALESCE(max(version),0)+1 AS value
                           FROM football_brief.video_model_use_policies
                           WHERE provider_key=%s AND model_key=%s""",
                        (policy["provider_key"], policy["model_key"]),
                    ).fetchone()["value"]
                )
                parent_id = active["id"] if active else None
                if active:
                    conn.execute(
                        """UPDATE football_brief.video_model_use_policies
                           SET status='retired',retired_by=%s,retired_at=now()
                           WHERE id=%s""",
                        (actor, active["id"]),
                    )
                inserted = conn.execute(
                    """INSERT INTO football_brief.video_model_use_policies
                       (provider_key,model_key,model_display_name,version,parent_policy_id,status,
                        license_name,license_spdx,terms_url,evidence_digest,evidence_recorded_at,
                        commercial_use_allowed,allowed_use_scopes,allowed_territories,
                        prohibited_territories,requires_written_clearance,metadata,created_by,
                        activated_by,activated_at)
                       VALUES (%s,%s,%s,%s,%s,'active',%s,%s,%s,%s,%s,%s,%s::text[],%s::text[],
                               %s::text[],%s,%s::jsonb,%s,%s,now()) RETURNING *""",
                    (
                        policy["provider_key"],
                        policy["model_key"],
                        policy["model_display_name"],
                        version,
                        parent_id,
                        policy["license_name"],
                        policy["license_spdx"],
                        policy["terms_url"],
                        evidence_digest,
                        datetime.now(timezone.utc),
                        policy["commercial_use_allowed"],
                        policy["allowed_use_scopes"],
                        policy["allowed_territories"],
                        policy["prohibited_territories"],
                        policy["requires_written_clearance"],
                        json.dumps(
                            {
                                **policy["metadata"],
                                "evidence_statement": policy["evidence"],
                                "evidence_document": _canonical_evidence(policy),
                            },
                            sort_keys=True,
                        ),
                        actor,
                        actor,
                    ),
                ).fetchone()
                results.append(
                    {
                        "provider_key": policy["provider_key"],
                        "model_key": policy["model_key"],
                        "policy_id": str(inserted["id"]),
                        "version": int(inserted["version"]),
                        "reused": False,
                    }
                )
    finally:
        database.close()
    return {"ok": True, "kind": "p113_model_policy_onboarding", "policies": results}


def main() -> int:
    print(json.dumps(onboard(), sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
