from __future__ import annotations

from pathlib import Path
from uuid import UUID

from elevenlabs import ElevenLabs

from src.application.assets.registry import AssetRegistryService
from src.application.media.narration_audit import NarrationAuditService
from src.application.media.voice_policy import VoicePolicyService
from src.config import Settings
from src.domain.narration_models import NarrationOutput
from src.domain.render_status import RenderMode


class ApprovedAudioAdapter:
    provider = "elevenlabs"

    def __init__(self, *, settings: Settings, registry: AssetRegistryService, voice_policy: VoicePolicyService, audit: NarrationAuditService) -> None:
        self.settings = settings
        self.registry = registry
        self.voice_policy = voice_policy
        self.audit = audit

    def synthesize(self, *, workflow_run_id: UUID, text: str, output_path: Path, mode: RenderMode, approved_voice_id: UUID | None, platform: str, language: str = "en", render_manifest_id: UUID | None = None, stage_execution_id: UUID | None = None, created_by: str = "approved-audio") -> NarrationOutput:
        raise NotImplementedError
