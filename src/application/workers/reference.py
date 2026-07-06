from __future__ import annotations

from src.application.workers.models import WorkerDefinition, WorkerHandlerResult


TRANSCRIPTION_WORKER = WorkerDefinition(
    name="transcription_stub",
    version="1.0.0",
    input_schema_name="TranscriptionInput",
    input_schema_version="1",
    output_schema_name="TranscriptionOutput",
    output_schema_version="1",
    timeout_seconds=30,
    idempotency_fields=("asset_id", "language", "audio_sha256"),
)

VOICE_WORKER = WorkerDefinition(
    name="voice_stub",
    version="1.0.0",
    input_schema_name="VoiceInput",
    input_schema_version="1",
    output_schema_name="VoiceOutput",
    output_schema_version="1",
    timeout_seconds=45,
    idempotency_fields=("script_hash", "voice_id", "language"),
)


def transcription_stub(input_payload: dict) -> WorkerHandlerResult:
    return WorkerHandlerResult(
        output={
            "text": input_payload.get("expected_text", "deterministic transcript"),
            "language": input_payload.get("language", "en"),
            "asset_id": input_payload.get("asset_id"),
        },
        provider_request_id="stub-transcription",
        units=1,
        unit_name="audio_file",
        metadata={"stub": True},
    )


def voice_stub(input_payload: dict) -> WorkerHandlerResult:
    return WorkerHandlerResult(
        output={
            "audio_asset_id": input_payload.get("audio_asset_id", "stub-audio"),
            "script_hash": input_payload.get("script_hash"),
            "voice_id": input_payload.get("voice_id"),
            "language": input_payload.get("language", "en"),
        },
        provider_request_id="stub-voice",
        units=1,
        unit_name="clip",
        metadata={"stub": True},
    )
