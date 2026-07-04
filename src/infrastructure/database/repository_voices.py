from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.asset_status import ApprovalStatus
from src.domain.voice_models import ApprovedVoice, ApprovedVoiceCreate
from src.infrastructure.database.repository_base import BaseRepository


class ApprovedVoiceRepository(BaseRepository[ApprovedVoice]):
    def create(self, data: ApprovedVoiceCreate) -> ApprovedVoice:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.approved_voices (
                provider,
                provider_voice_id,
                display_name,
                voice_type,
                approval_status,
                consent_evidence_asset_id,
                allowed_languages,
                allowed_platforms,
                prohibited_uses,
                expires_at,
                approved_by,
                approved_at,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider, provider_voice_id)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                voice_type = EXCLUDED.voice_type,
                approval_status = EXCLUDED.approval_status,
                consent_evidence_asset_id = EXCLUDED.consent_evidence_asset_id,
                allowed_languages = EXCLUDED.allowed_languages,
                allowed_platforms = EXCLUDED.allowed_platforms,
                prohibited_uses = EXCLUDED.prohibited_uses,
                expires_at = EXCLUDED.expires_at,
                approved_by = EXCLUDED.approved_by,
                approved_at = EXCLUDED.approved_at,
                metadata = EXCLUDED.metadata
            RETURNING *
            """,
            (
                data.provider,
                data.provider_voice_id,
                data.display_name,
                data.voice_type.value,
                data.approval_status.value,
                data.consent_evidence_asset_id,
                data.allowed_languages,
                data.allowed_platforms,
                data.prohibited_uses,
                data.expires_at,
                data.approved_by,
                data.approved_at,
                Jsonb(data.metadata),
            ),
        ).fetchone()
        return self.required(row, ApprovedVoice, "approved voice")

    def get(self, voice_id: UUID) -> ApprovedVoice:
        row = self.conn.execute(
            "SELECT * FROM football_brief.approved_voices WHERE id = %s",
            (voice_id,),
        ).fetchone()
        return self.required(row, ApprovedVoice, "approved voice")

    def get_by_provider_voice_id(
        self,
        provider: str,
        provider_voice_id: str,
    ) -> ApprovedVoice | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM football_brief.approved_voices
            WHERE provider = %s AND provider_voice_id = %s
            """,
            (provider, provider_voice_id),
        ).fetchone()
        return ApprovedVoice.model_validate(row) if row else None

    def list_by_status(self, status: ApprovalStatus) -> list[ApprovedVoice]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM football_brief.approved_voices
            WHERE approval_status = %s
            ORDER BY provider, display_name
            """,
            (status.value,),
        ).fetchall()
        return [ApprovedVoice.model_validate(row) for row in rows]
