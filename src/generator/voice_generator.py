"""Generate voiceover via ElevenLabs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from elevenlabs import ElevenLabs

from src.application.media.models import VoiceUseRequest
from src.application.media.voice_policy import VoicePolicyService
from src.config import Settings
from src.domain.render_status import RenderMode
from src.extractor.ffmpeg_clipper import is_valid_audio_file
from src.generator.models import ExplainerPlan, ProductionPlan

VOICE_PLAN_ERROR = (
    "ElevenLabs free API plans cannot use library voices. "
    "Run: python -m src.cli list-voices "
    "Then set ELEVENLABS_VOICE_ID in .env to a premade voice from YOUR account."
)

# Categories that typically work on free/creator API plans (account voices)
USABLE_CATEGORIES = frozenset({"premade", "cloned", "generated", "professional"})


def list_available_voices(api_key: str) -> list[dict[str, str]]:
    client = ElevenLabs(api_key=api_key)
    response = client.voices.get_all(show_legacy=True)
    voices = []
    for voice in response.voices:
        voices.append(
            {
                "name": voice.name,
                "voice_id": voice.voice_id,
                "category": getattr(voice, "category", "") or "",
            }
        )
    return voices


def list_usable_voices(api_key: str) -> list[dict[str, str]]:
    """Voices on your account that work with the API (premade / cloned)."""
    voices = list_available_voices(api_key)
    usable: list[dict[str, str]] = []
    for voice in voices:
        category = voice["category"].lower()
        if not category or category in USABLE_CATEGORIES:
            usable.append(voice)
    return usable or voices


def resolve_voice_id(api_key: str, preferred: str | None = None) -> tuple[str, str]:
    """
    Pick a voice ID from the user's account. Rejects library-only IDs not on the account.
    Returns (voice_id, voice_name).
    """
    usable = list_usable_voices(api_key)
    if not usable:
        raise ValueError(
            "No voices found on your ElevenLabs account. "
            "Open elevenlabs.io → Voices and add a premade voice to your account."
        )

    by_id = {v["voice_id"]: v for v in usable}

    if preferred and preferred in by_id:
        return preferred, by_id[preferred]["name"]

    if preferred:
        print(
            f"  Voice ID {preferred} is not on your account (or is library-only). "
            f"Picking a premade voice from your account instead.",
            flush=True,
        )

    for voice in usable:
        if voice["category"].lower() == "premade":
            return voice["voice_id"], voice["name"]

    first = usable[0]
    return first["voice_id"], first["name"]


def _synthesize_segment(
    client: ElevenLabs,
    voice_id: str,
    text: str,
    model_id: str,
    out_path: Path,
) -> None:
    temp_path = out_path.with_suffix(".tmp.mp3")
    try:
        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="mp3_44100_128",
        )
        with temp_path.open("wb") as f:
            for chunk in audio_stream:
                f.write(chunk)

        if not is_valid_audio_file(temp_path):
            raise RuntimeError(f"ElevenLabs returned invalid audio for {out_path.name}")

        temp_path.replace(out_path)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        if out_path.exists() and not is_valid_audio_file(out_path):
            out_path.unlink()
        message = str(exc).lower()
        if "402" in message or "payment_required" in message or "paid_plan" in message:
            raise ValueError(VOICE_PLAN_ERROR) from exc
        raise


def _voice_for_mode(
    *,
    settings: Settings,
    mode: RenderMode,
    platform: str,
    approved_voice_id: UUID | None,
    voice_policy: VoicePolicyService | None,
) -> tuple[str, str]:
    if mode == RenderMode.PUBLISH:
        if voice_policy is None or approved_voice_id is None:
            raise ValueError("Publish voiceover requires an approved internal voice ID")
        decision = voice_policy.authorize(
            VoiceUseRequest(
                mode=mode,
                provider="elevenlabs",
                approved_voice_id=approved_voice_id,
                language="en",
                platform=platform,
                requested_by="voice-generator",
            )
        )
        return decision.provider_voice_id, decision.voice.display_name if decision.voice else decision.provider_voice_id

    if voice_policy is not None and approved_voice_id is not None:
        decision = voice_policy.authorize(
            VoiceUseRequest(
                mode=mode,
                provider="elevenlabs",
                approved_voice_id=approved_voice_id,
                language="en",
                platform=platform,
                requested_by="voice-generator",
            )
        )
        return decision.provider_voice_id, decision.voice.display_name if decision.voice else decision.provider_voice_id

    return resolve_voice_id(settings.elevenlabs_api_key, settings.elevenlabs_voice_id or None)


def generate_voiceovers(
    plan: ProductionPlan,
    output_dir: Path,
    settings: Settings,
    force_regenerate: bool = False,
    mode: RenderMode = RenderMode.PREVIEW,
    approved_voice_id: UUID | None = None,
    voice_policy: VoicePolicyService | None = None,
    platform: str = "youtube",
) -> dict[int, Path]:
    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set. Add it to your .env file.")

    voice_id, voice_name = _voice_for_mode(
        settings=settings,
        mode=mode,
        platform=platform,
        approved_voice_id=approved_voice_id,
        voice_policy=voice_policy,
    )
    settings.elevenlabs_voice_id = voice_id
    print(f"  Using voice: {voice_name} ({voice_id})", flush=True)

    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[int, Path] = {}

    for segment in plan.narrated_segments():
        order = segment.order
        out_path = output_dir / f"narration_{order:02d}.mp3"
        if not force_regenerate and out_path.exists() and is_valid_audio_file(out_path):
            print(f"  Reusing voice: narration_{order:02d}.mp3", flush=True)
            paths[order] = out_path
            continue

        if out_path.exists():
            out_path.unlink()

        print(f"  Generating voice: narration_{order:02d}.mp3", flush=True)
        _synthesize_segment(
            client=client,
            voice_id=voice_id,
            text=segment.narration,
            model_id=settings.elevenlabs_model,
            out_path=out_path,
        )
        paths[order] = out_path

    return paths


def generate_explainer_voiceovers(
    plan: ExplainerPlan,
    output_dir: Path,
    settings: Settings,
    force_regenerate: bool = False,
    on_section_complete: Callable[[str], None] | None = None,
) -> tuple[dict[str, Path], str, str]:
    """One narration MP3 per section. Returns (paths, voice_id, voice_name)."""
    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set. Add it to your .env file.")

    voice_id, voice_name = resolve_voice_id(
        settings.elevenlabs_api_key, settings.elevenlabs_voice_id or None
    )
    settings.elevenlabs_voice_id = voice_id
    print(f"  Using voice: {voice_name} ({voice_id})", flush=True)

    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for section in plan.narrated_sections():
        out_path = output_dir / f"narration_{section.id}.mp3"
        if not force_regenerate and out_path.exists() and is_valid_audio_file(out_path):
            print(f"  Reusing voice: narration_{section.id}.mp3", flush=True)
            paths[section.id] = out_path
            if on_section_complete:
                on_section_complete(section.id)
            continue

        if out_path.exists():
            out_path.unlink()

        print(f"  Generating voice: narration_{section.id}.mp3", flush=True)
        _synthesize_segment(
            client=client,
            voice_id=voice_id,
            text=section.narration,
            model_id=settings.elevenlabs_model,
            out_path=out_path,
        )
        paths[section.id] = out_path
        if on_section_complete:
            on_section_complete(section.id)

    return paths, voice_id, voice_name
