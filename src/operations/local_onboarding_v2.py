from __future__ import annotations

import json

from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.local_onboarding import BRANDS, LocalOnboarding


class AlwaysOnLocalOnboarding(LocalOnboarding):
    """Extend the existing local seed with one active, safe visual preset per brand."""

    def run(self) -> dict:
        result = super().run()
        presets: dict[str, dict] = {}
        with self.database.transaction() as conn:
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
                           VALUES (%s,'local-default','Local SDXL vertical preset',%s,%s,'active',
                                   %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                                   %s,%s::jsonb,%s,now()) RETURNING *""",
                        (
                            row["profile_id"],
                            int(latest["version"]) + 1 if latest else 1,
                            latest["id"] if latest else None,
                            json.dumps({"mood": "natural documentary", "contrast": "controlled cinematic"}),
                            json.dumps({"accurate_anatomy": True, "single_clear_subject": True}),
                            json.dumps({"habitat_consistency": True, "original_composition": True}),
                            json.dumps({"portrait": True, "camera_motion": "none_in_keyframe"}),
                            json.dumps({"naturalistic": True, "avoid_harsh_artificial_glow": True}),
                            json.dumps({"aspect_ratio": "9:16", "safe_text_area": True}),
                            "text, watermark, logo, duplicate subject, malformed anatomy, extra limbs, cropped face",
                            json.dumps(["copyrighted character", "brand logo", "graphic violence"]),
                            self.admin_id,
                        ),
                    ).fetchone()
                presets[spec["slug"]] = {"id": str(preset["id"]), "status": preset["status"]}
        result["visual_presets"] = presets
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
