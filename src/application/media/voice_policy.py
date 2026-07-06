from __future__ import annotations

from datetime import datetime, timezone

from src.application.media.models import VoiceUseDecision, VoiceUseRequest
from src.application.media.policy_errors import VoicePolicyFailure
from src.domain.asset_status import ApprovalStatus
from src.domain.render_status import RenderMode
from src.domain.voice_models import ApprovedVoice, VoiceType
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class VoicePolicyService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def authorize(self, request: VoiceUseRequest, *, now: datetime | None = None) -> VoiceUseDecision:
        checked_at = now or datetime.now(timezone.utc)
        with unit_of_work(self.database) as uow:
            voice = None
            if request.approved_voice_id is not None:
                voice = uow.approved_voices.get(request.approved_voice_id)
            elif request.provider_voice_id is not None:
                voice = uow.approved_voices.get_by_provider_voice_id(request.provider, request.provider_voice_id)

        if request.mode == RenderMode.PUBLISH:
            if voice is None:
                raise VoicePolicyFailure("Publish narration requires an approved internal voice ID")
            self._require_publishable(voice, request, checked_at)
            return VoiceUseDecision(voice=voice, provider=voice.provider, provider_voice_id=voice.provider_voice_id, development_voice=False, mode=request.mode)

        if voice is not None:
            self._require_preview_allowed(voice, request, checked_at)
            return VoiceUseDecision(voice=voice, provider=voice.provider, provider_voice_id=voice.provider_voice_id, development_voice=voice.preview_only, mode=request.mode)

        if not request.allow_development_voice or not request.provider_voice_id:
            raise VoicePolicyFailure("Preview narration with an unknown provider voice must be explicitly marked as development")
        return VoiceUseDecision(voice=None, provider=request.provider, provider_voice_id=request.provider_voice_id, development_voice=True, mode=request.mode)
