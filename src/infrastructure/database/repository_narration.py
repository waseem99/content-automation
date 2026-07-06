from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.narration_models import NarrationOutput, NarrationOutputCreate
from src.infrastructure.database.repository_base import BaseRepository


class NarrationOutputRepository(BaseRepository[NarrationOutput]):
    def create(self, data: NarrationOutputCreate) -> NarrationOutput:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.narration_outputs (
                workflow_run_id, render_manifest_id, stage_execution_id,
                mode, platform, language, text_hash, text_length,
                approved_voice_id, provider, provider_voice_id,
                provider_request_id, model_id, output_asset_id, output_sha256,
                created_by, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.workflow_run_id,
                data.render_manifest_id,
                data.stage_execution_id,
                data.mode.value,
                data.platform,
                data.language,
                data.text_hash,
                data.text_length,
                data.approved_voice_id,
                data.provider,
                data.provider_voice_id,
                data.provider_request_id,
                data.model_id,
                data.output_asset_id,
                data.output_sha256,
                data.created_by,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, NarrationOutput, "narration output")

    def list_for_manifest(self, render_manifest_id: UUID) -> list[NarrationOutput]:
        rows = self.conn.execute(
            """
            SELECT * FROM football_brief.narration_outputs
            WHERE render_manifest_id = %s
            ORDER BY created_at, id
            """,
            (render_manifest_id,),
        ).fetchall()
        return [NarrationOutput.model_validate(row) for row in rows]
