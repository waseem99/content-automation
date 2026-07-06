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
                raise VoicePolicyFailure("Publish narration requires an approved internal voice ID; raw provider IDs are not approval")
            self._require_publishable(voice, request, checked_at)
            return VoiceUseDecision(voice=voice, provider=voice.provider, provider_voice_id=voice.provider_voice_id, development_voice=False, mode=request.mode)

        if voice is not None:
            self._require_preview_allowed(voice, request, checked_at)
            return VoiceUseDecision(voice=voice, provider=voice.provider, provider_voice_id=voice.provider_voice_id, development_voice=voice.preview_only, mode=request.mode)

        if not request.allow_development_voice or not request.provider_voice_id:
            raise VoicePolicyFailure("Preview narration with an unknown provider voice must be explicitly marked as development")
        return VoiceUseDecision(voice=None, provider=request.provider, provider_voice_id=request.provider_voice_id, development_voice=True, mode=request.mode)

    def _require_publishable(self, voice: ApprovedVoice, request: VoiceUseRequest, now: datetime) -> None:
        self._require_common(voice, request, now)
        if voice.preview_only:
            raise VoicePolicyFailure("Preview-only development voice cannot be used for publish")
        if voice.approval_status != ApprovalStatus.APPROVED:
            raise VoicePolicyFailure("Voice is not approved")
        if voice.voice_type == VoiceType.CLONED and voice.consent_evidence_asset_id is None:
            raise VoicePolicyFailure("Cloned voice requires consent evidence")

    def _require_preview_allowed(self, voice: ApprovedVoice, request: VoiceUseRequest, now: datetime) -> None:
        if voice.approval_status in {ApprovalStatus.REVOKED, ApprovalStatus.EXPIRED}:
            raise VoicePolicyFailure("Revoked or expired voice cannot be used")
        self._require_common(voice, request, now)

    @staticmethod
    def _require_common(voice: ApprovedVoice, request: VoiceUseRequest, now: datetime) -> None:
        if voice.provider != request.provider:
            raise VoicePolicyFailure("Voice provider does not match request")
        if request.provider_voice_id and voice.provider_voice_id != request.provider_voice_id:
            raise VoicePolicyFailure("Provider voice ID does not match approval")
        if voice.expires_at is not None and voice.expires_at <= now:
            raise VoicePolicyFailure("Voice approval is expired")
        languages = {item.strip().lower() for item in voice.allowed_languages}
        if languages and request.language not in languages:
            raise VoicePolicyFailure("Voice is not approved for the requested language")
        platforms = {item.strip().lower() for item in voice.allowed_platforms if item.strip()}
        if platforms and request.platform not in platforms:
            raise VoicePolicyFailure("Voice is not approved for the requested platform")
        blocked = {item.strip().lower() for item in voice.prohibited_uses}
        if request.use_case in blocked or ("real_person_mimicry" in request.use_case and "real_person_mimicry" in blocked):
            raise VoicePolicyFailure("Voice use is prohibited")
