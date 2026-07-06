from __future__ import annotations

import hashlib

from src.application.media.models import VoiceSynthesisAuditRequest
from src.domain.narration_models import NarrationOutput, NarrationOutputCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class NarrationAuditService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record(self, request: VoiceSynthesisAuditRequest) -> NarrationOutput:
        with unit_of_work(self.database) as uow:
            return uow.narration_outputs.create(
                NarrationOutputCreate(
                    workflow_run_id=request.workflow_run_id,
                    render_manifest_id=request.render_manifest_id,
                    stage_execution_id=request.stage_execution_id,
                    mode=request.mode,
                    platform=request.platform,
                    language=request.language,
                    text_hash=text_hash(request.text),
                    text_length=len(request.text),
                    approved_voice_id=request.approved_voice_id,
                    provider=request.provider,
                    provider_voice_id=request.provider_voice_id,
                    provider_request_id=request.provider_request_id,
                    model_id=request.model_id,
                    output_asset_id=request.output_asset_id,
                    output_sha256=request.output_sha256,
                    created_by=request.created_by,
                    metadata=request.metadata,
                )
            )
