from __future__ import annotations

import json
import os

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.local_onboarding import BRANDS, LocalOnboarding
from src.operator_api.access import OperatorRole, expand_operator_roles


PUBLIC_OPERATORS = (
    ("LOCAL_SUPER_ADMIN_OPERATOR_ID", "local-super-admin", "Local Super Administrator", OperatorRole.SUPER_ADMIN),
    ("LOCAL_ADMIN_OPERATOR_ID", "local-admin", "Local Administrator", OperatorRole.ADMIN),
    ("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer", "Local Reviewer", OperatorRole.REVIEWER),
)


class AlwaysOnLocalOnboarding(LocalOnboarding):
    """Seed safe local production defaults and the simplified three-role model."""

    def run(self) -> dict:
        # Preserve all historical onboarding behavior, then reconcile the public
        # role model without deleting any production, artifact or review data.
        result = super().run()
        presets: dict[str, dict] = {}
        operators: dict[str, dict] = {}
        review_policies: dict[str, dict] = {}
        with self.database.transaction() as conn:
            brands = conn.execute(
                "SELECT id,slug,display_name FROM football_brief.brands WHERE active=true ORDER BY slug"
            ).fetchall()

            for env_name, default_id, default_name, public_role in PUBLIC_OPERATORS:
                operator_id = os.getenv(env_name, default_id)
                display_name = os.getenv(env_name.replace("_ID", "_DISPLAY_NAME"), default_name)
                row = conn.execute(
                    """INSERT INTO football_brief.operator_users
                       (operator_id,display_name,active,created_by)
                       VALUES (%s,%s,true,%s)
                       ON CONFLICT (operator_id) DO UPDATE SET
                         display_name=EXCLUDED.display_name,active=true
                       RETURNING *""",
                    (operator_id, display_name, self.admin_id),
                ).fetchone()
                conn.execute(
                    "DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s",
                    (row["id"],),
                )
                internal_roles = expand_operator_roles((public_role,))
                for role in sorted(internal_roles, key=lambda value: value.value):
                    conn.execute(
                        """INSERT INTO football_brief.operator_user_roles
                           (operator_user_id,role,assigned_by) VALUES (%s,%s,%s)""",
                        (row["id"], role.value, self.admin_id),
                    )
                conn.execute(
                    "DELETE FROM football_brief.operator_brand_assignments WHERE operator_user_id=%s",
                    (row["id"],),
                )
                for brand in brands:
                    conn.execute(
                        """INSERT INTO football_brief.operator_brand_assignments
                           (operator_user_id,brand_id,assigned_by)
                           VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (row["id"], brand["id"], self.admin_id),
                    )
                operators[operator_id] = {
                    "operator_id": operator_id,
                    "display_name": display_name,
                    "roles": [public_role.value],
                    "internal_roles": sorted(role.value for role in internal_roles),
                }

            # P110 seeds one explicit policy per active brand after the public Admin
            # audit identity exists. Re-runs preserve any deliberate policy change.
            for brand in brands:
                policy = conn.execute(
                    """SELECT * FROM football_brief.brand_review_policies
                       WHERE brand_id=%s AND active=true
                       ORDER BY version DESC LIMIT 1""",
                    (brand["id"],),
                ).fetchone()
                if not policy:
                    version = conn.execute(
                        """SELECT COALESCE(max(version),0)+1 AS value
                           FROM football_brief.brand_review_policies WHERE brand_id=%s""",
                        (brand["id"],),
                    ).fetchone()["value"]
                    policy = conn.execute(
                        """INSERT INTO football_brief.brand_review_policies
                           (brand_id,version,policy_key,active,rationale_required_for_override,
                            created_by,activated_at,metadata)
                           VALUES (%s,%s,'admin_self_review_allowed',true,false,%s,now(),%s::jsonb)
                           RETURNING *""",
                        (
                            brand["id"],
                            version,
                            self.admin_id,
                            json.dumps(
                                {
                                    "p110_onboarding": True,
                                    "independent_reviewer_available": True,
                                    "final_release_gates_preserved": True,
                                }
                            ),
                        ),
                    ).fetchone()
                review_policies[str(brand["slug"])] = {
                    "id": str(policy["id"]),
                    "version": int(policy["version"]),
                    "policy_key": str(policy["policy_key"]),
                }

            # Dedicated non-login worker identities may claim only P87 jobs. They
            # have no API keys and cannot review, approve, manage users, release or publish.
            for env_name, default_id, display_name in (
                ("HIGGSFIELD_WORKER_OPERATOR_ID", "higgsfield-worker", "Higgsfield Managed Renderer"),
                ("LOCAL_VIDEO_WORKER_OPERATOR_ID", "local-video-worker", "Local Video Renderer"),
            ):
                worker_id = os.getenv(env_name, default_id)
                worker = conn.execute(
                    """INSERT INTO football_brief.operator_users
                       (operator_id,display_name,active,created_by)
                       VALUES (%s,%s,true,%s)
                       ON CONFLICT (operator_id) DO UPDATE SET
                         display_name=EXCLUDED.display_name,active=true
                       RETURNING *""",
                    (worker_id, display_name, self.admin_id),
                ).fetchone()
                conn.execute(
                    "DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s",
                    (worker["id"],),
                )
                conn.execute(
                    """INSERT INTO football_brief.operator_user_roles
                       (operator_user_id,role,assigned_by) VALUES (%s,'producer',%s)""",
                    (worker["id"], self.admin_id),
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
                        (worker["id"], brand["id"], self.admin_id),
                    )
                operators[worker_id] = {
                    "operator_id": worker_id,
                    "display_name": display_name,
                    "roles": ["internal_worker"],
                    "internal_roles": ["producer"],
                    "api_key_created": False,
                }

            # Old local keys are removed by the launcher upgrade. Keep their
            # historical audit records but prevent those identities from signing in.
            conn.execute(
                """UPDATE football_brief.operator_users SET active=false
                   WHERE operator_id IN ('local-producer','local-publisher')"""
            )

            for spec in BRANDS:
                row = conn.execute(
                    """SELECT bp.id AS profile_id,b.id AS brand_id
                       FROM football_brief.brands b
                       JOIN football_brief.brand_profiles bp ON bp.brand_id=b.id AND bp.status='active'
                       WHERE b.slug=%s""",
                    (spec["slug"],),
                ).fetchone()
                if not row:
                    continue
                preset = conn.execute(
                    """SELECT * FROM football_brief.brand_visual_presets
                       WHERE brand_profile_id=%s AND preset_key='local-default' AND status='active'
                       ORDER BY version DESC LIMIT 1""",
                    (row["profile_id"],),
                ).fetchone()
                if not preset:
                    latest = conn.execute(
                        """SELECT id,version FROM football_brief.brand_visual_presets
                           WHERE brand_profile_id=%s AND preset_key='local-default'
                           ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                        (row["profile_id"],),
                    ).fetchone()
                    conn.execute(
                        """UPDATE football_brief.brand_visual_presets
                           SET status='retired'
                           WHERE brand_profile_id=%s AND preset_key='local-default' AND status='active'""",
                        (row["profile_id"],),
                    )
                    preset = conn.execute(
                        """INSERT INTO football_brief.brand_visual_presets
                           (brand_profile_id,preset_key,display_name,version,parent_preset_id,status,palette,
                            subject_rules,environment_rules,camera_rules,lighting_rules,
                            framing_rules,negative_prompt,exclusions,created_by,activated_at)
                           VALUES (%s,'local-default','Local SDXL multi-format preset',%s,%s,'active',
                                   %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                                   %s,%s::jsonb,%s,now()) RETURNING *""",
                        (
                            row["profile_id"],
                            int(latest["version"]) + 1 if latest else 1,
                            latest["id"] if latest else None,
                            json.dumps({"mood": "natural documentary", "contrast": "controlled cinematic"}),
                            json.dumps({"accurate_anatomy": True, "single_clear_subject": True}),
                            json.dumps({"habitat_consistency": True, "original_composition": True}),
                            json.dumps({"portrait": True, "landscape": True, "camera_motion": "none_in_keyframe"}),
                            json.dumps({"naturalistic": True, "avoid_harsh_artificial_glow": True}),
                            json.dumps({"aspect_ratios": ["16:9", "4:5", "9:16"], "safe_text_area": True}),
                            "text, watermark, logo, duplicate subject, malformed anatomy, extra limbs, cropped face",
                            json.dumps(["copyrighted character", "brand logo", "graphic violence"]),
                            self.admin_id,
                        ),
                    ).fetchone()
                presets[spec["slug"]] = {"id": str(preset["id"]), "status": preset["status"]}
        result["operators"] = operators
        result["role_model"] = ["super_admin", "admin", "reviewer"]
        result["visual_presets"] = presets
        result["review_policies"] = review_policies
        return result


def main() -> int:
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        result = AlwaysOnLocalOnboarding(database).run()
    finally:
        database.close()
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
