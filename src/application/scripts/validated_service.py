from __future__ import annotations

from uuid import UUID, uuid4

from src.application.scripts.service import ScriptReviewService, _json


class ValidatedScriptReviewService(ScriptReviewService):
    """P89 service with JSON-safe full-graph revision copying."""

    @staticmethod
    def _copy_children(conn, *, old_version_id: UUID, new_version_id: UUID) -> None:
        section_rows = conn.execute(
            "SELECT * FROM football_brief.script_sections WHERE script_version_id=%s ORDER BY sequence",
            (old_version_id,),
        ).fetchall()
        section_map: dict[UUID, UUID] = {}
        for row in section_rows:
            new_id = uuid4()
            section_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_sections
                   (id, script_version_id, sequence, section_key, section_type, text,
                    target_duration_seconds, estimated_duration_seconds, word_count)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id,
                    new_version_id,
                    row["sequence"],
                    row["section_key"],
                    row["section_type"],
                    row["text"],
                    row["target_duration_seconds"],
                    row["estimated_duration_seconds"],
                    row["word_count"],
                ),
            )

        for row in conn.execute(
            "SELECT * FROM football_brief.script_scene_plan_entries WHERE script_version_id=%s ORDER BY sequence",
            (old_version_id,),
        ).fetchall():
            conn.execute(
                """INSERT INTO football_brief.script_scene_plan_entries
                   (script_version_id, script_section_id, sequence, scene_key,
                    narration_text, visual_brief, on_screen_text,
                    target_duration_seconds, source_requirements)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    new_version_id,
                    section_map[row["script_section_id"]],
                    row["sequence"],
                    row["scene_key"],
                    row["narration_text"],
                    row["visual_brief"],
                    row["on_screen_text"],
                    row["target_duration_seconds"],
                    _json(row["source_requirements"] or []),
                ),
            )

        claim_map: dict[UUID, UUID] = {}
        for row in conn.execute(
            "SELECT * FROM football_brief.script_claims WHERE script_version_id=%s ORDER BY claim_key",
            (old_version_id,),
        ).fetchall():
            new_id = uuid4()
            claim_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_claims
                   (id, script_version_id, script_section_id, claim_key, claim_text,
                    claim_type, confidence, sensitivity, support_status, wording_limitations)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id,
                    new_version_id,
                    section_map[row["script_section_id"]],
                    row["claim_key"],
                    row["claim_text"],
                    row["claim_type"],
                    row["confidence"],
                    row["sensitivity"],
                    row["support_status"],
                    row["wording_limitations"],
                ),
            )

        source_map: dict[UUID, UUID] = {}
        for row in conn.execute(
            "SELECT * FROM football_brief.script_sources WHERE script_version_id=%s ORDER BY source_key",
            (old_version_id,),
        ).fetchall():
            new_id = uuid4()
            source_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_sources
                   (id, script_version_id, source_key, source_type, title, publisher,
                    canonical_url, published_on, accessed_at, quality_score,
                    rights_declaration, permitted_use, evidence_digest, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id,
                    new_version_id,
                    row["source_key"],
                    row["source_type"],
                    row["title"],
                    row["publisher"],
                    row["canonical_url"],
                    row["published_on"],
                    row["accessed_at"],
                    row["quality_score"],
                    row["rights_declaration"],
                    row["permitted_use"],
                    row["evidence_digest"],
                    row["notes"],
                ),
            )

        for row in conn.execute(
            "SELECT * FROM football_brief.script_claim_sources WHERE script_version_id=%s",
            (old_version_id,),
        ).fetchall():
            conn.execute(
                """INSERT INTO football_brief.script_claim_sources
                   (script_version_id, claim_id, source_id, support_type, locator, support_note)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    new_version_id,
                    claim_map[row["claim_id"]],
                    source_map[row["source_id"]],
                    row["support_type"],
                    row["locator"],
                    row["support_note"],
                ),
            )
