"""CLI entry point for clip extraction pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from src.analyzer.audio_analyzer import detect_energy_spikes
from src.analyzer.scene_detector import detect_scenes
from src.analyzer.topic_matcher import score_transcript_segments
from src.analyzer.transcriber import transcribe_audio
from src.config import Settings, get_settings
from src.extractor.ffmpeg_clipper import (
    extract_audio_wav,
    extract_clips,
    format_timestamp,
    probe_duration,
    slugify_label,
)
from src.ranker.moment_ranker import rank_moments
from src.producer import run_production
from src.explainer_producer import run_explainer_production
from src.concepts.loader import load_concept
from src.extractor.clip_pool import build_clip_pool

app = typer.Typer(help="YouTube automation — clip extraction from match videos.")


def _create_run_dir(video_path: Path, output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{video_path.stem}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_manifest(
    run_dir: Path,
    video_path: Path,
    topic: str,
    windows: list,
    clip_paths: list[Path],
) -> Path:
    manifest = {
        "source_video": str(video_path.resolve()),
        "topic": topic,
        "created_at": datetime.now().isoformat(),
        "clips": [],
    }
    for window, clip_path in zip(windows, clip_paths):
        manifest["clips"].append(
            {
                "file": clip_path.name,
                "start": format_timestamp(window.start),
                "end": format_timestamp(window.end),
                "start_sec": round(window.start, 3),
                "end_sec": round(window.end, 3),
                "score": round(window.score, 4),
                "label": window.label,
                "source_text": window.source_text,
            }
        )
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


@app.command("extract")
def extract(
    video: Path = typer.Option(..., "--video", "-v", help="Path to source video"),
    topic: str = typer.Option(..., "--topic", "-t", help="Topic for moment matching"),
    count: int = typer.Option(4, "--count", "-c", help="Number of clips to extract"),
    duration: float = typer.Option(7.0, "--duration", "-d", help="Clip length in seconds"),
    min_gap: float = typer.Option(15.0, "--min-gap", help="Minimum gap between clips"),
    output_dir: Path = typer.Option(Path("data/output"), "--output-dir", "-o"),
    max_duration: float | None = typer.Option(
        None, "--max-duration", help="Analyze only first N seconds (for testing)"
    ),
    whisper_model: str = typer.Option("small", "--whisper-model"),
    whisper_device: str = typer.Option("cpu", "--whisper-device"),
) -> None:
    """Analyze a video and extract the top ranked moment clips."""
    if not video.exists():
        typer.secho(f"Video not found: {video}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    settings = get_settings()
    settings.clip_count = count
    settings.clip_duration = duration
    settings.min_gap = min_gap
    settings.output_dir = output_dir
    settings.max_duration = max_duration
    settings.whisper_model = whisper_model
    settings.whisper_device = whisper_device

    run_dir = _create_run_dir(video, output_dir)
    typer.echo(f"Output folder: {run_dir}")

    typer.echo("Probing video duration...")
    full_duration = probe_duration(video)
    analyze_duration = min(full_duration, max_duration) if max_duration else full_duration
    typer.echo(f"Video duration: {format_timestamp(full_duration)} (analyzing {format_timestamp(analyze_duration)})")

    typer.echo("Extracting audio for analysis...")
    wav_path = run_dir / "analysis_audio.wav"
    extract_audio_wav(video, wav_path, max_duration=max_duration)

    typer.echo("Detecting scenes...")
    scenes = detect_scenes(video, threshold=settings.scene_threshold)
    if max_duration is not None:
        scenes = [s for s in scenes if s.time_sec <= max_duration]
    typer.echo(f"Found {len(scenes)} scene boundaries")

    typer.echo("Detecting crowd energy spikes...")
    energy_spikes = detect_energy_spikes(
        wav_path,
        window_sec=settings.energy_window_sec,
        top_percentile=settings.energy_top_percentile,
    )
    typer.echo(f"Found {len(energy_spikes)} energy spikes")

    typer.echo(f"Transcribing audio (model={whisper_model}, device={whisper_device})...")
    transcript = transcribe_audio(
        wav_path,
        model_size=whisper_model,
        device=whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    typer.echo(f"Transcribed {len(transcript)} speech segments")

    typer.echo("Scoring transcript against topic...")
    transcript_hits = score_transcript_segments(transcript, topic)
    typer.echo(f"Found {len(transcript_hits)} topic-relevant segments")

    typer.echo("Ranking moments...")
    windows = rank_moments(
        scenes=scenes,
        energy_spikes=energy_spikes,
        transcript_hits=transcript_hits,
        video_duration=analyze_duration,
        settings=settings,
    )
    if not windows:
        typer.secho("No moments selected.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo("Selected moments:")
    for index, window in enumerate(windows, start=1):
        typer.echo(
            f"  {index}. {format_timestamp(window.start)} - {format_timestamp(window.end)} "
            f"[{slugify_label(window.label)}] score={window.score:.3f}"
        )

    typer.echo("Extracting clips with ffmpeg...")
    clip_paths = extract_clips(video, run_dir, windows)
    manifest_path = _write_manifest(run_dir, video, topic, windows, clip_paths)

    typer.secho(f"Done. {len(clip_paths)} clips saved to {run_dir}", fg=typer.colors.GREEN)
    typer.echo(f"Manifest: {manifest_path}")


def _expand_video_glob(videos: str) -> list[Path]:
    if "*" in videos or "?" in videos:
        return sorted(Path().glob(videos))
    path = Path(videos)
    if path.is_dir():
        return sorted(
            list(path.glob("*.mp4"))
            + list(path.glob("*.mkv"))
            + list(path.glob("*.mov"))
            + list(path.glob("*.webm"))
        )
    return [path]


@app.command("extract-batch")
def extract_batch(
    concept: Path = typer.Option(..., "--concept", help="Concept YAML file"),
    videos: str = typer.Option(..., "--videos", help="Video path, directory, or glob"),
    campaign_dir: Path = typer.Option(..., "--campaign-dir", help="Campaign output directory"),
    max_duration: float | None = typer.Option(
        None, "--max-duration", help="Analyze only first N seconds per video (testing)"
    ),
    whisper_model: str = typer.Option("small", "--whisper-model"),
    whisper_device: str = typer.Option("cpu", "--whisper-device"),
) -> None:
    """Extract clips from multiple videos into a shared clip pool."""
    if not concept.exists():
        typer.secho(f"Concept not found: {concept}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    video_paths = _expand_video_glob(videos)
    if not video_paths:
        typer.secho(f"No videos matched: {videos}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    concept_def = load_concept(concept)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "concept.yaml").write_text(
        concept.read_text(encoding="utf-8"), encoding="utf-8"
    )

    settings = get_settings()
    settings.whisper_model = whisper_model
    settings.whisper_device = whisper_device

    typer.echo(f"Campaign: {campaign_dir}")
    typer.echo(f"Concept: {concept_def.title}")
    typer.echo(f"Videos: {len(video_paths)}")

    def log(msg: str) -> None:
        typer.echo(msg)

    try:
        manifest_path = build_clip_pool(
            videos=video_paths,
            concept=concept_def,
            campaign_dir=campaign_dir,
            settings=settings,
            max_duration=max_duration,
            progress=log,
        )
    except Exception as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.secho(f"Done. Clip pool saved to {manifest_path}", fg=typer.colors.GREEN)


@app.command("produce-explainer")
def produce_explainer(
    campaign_dir: Path = typer.Option(..., "--campaign-dir", help="Campaign folder with clip_pool/"),
    concept: Path = typer.Option(..., "--concept", help="Concept YAML file"),
    skip_images: bool = typer.Option(False, "--skip-images"),
    skip_voice: bool = typer.Option(False, "--skip-voice"),
    skip_assembly: bool = typer.Option(False, "--skip-assembly"),
    bg_music: Path | None = typer.Option(None, "--bg-music"),
    bg_music_volume: float = typer.Option(0.12, "--bg-music-volume"),
    voice_id: str | None = typer.Option(
        None,
        "--voice-id",
        help="ElevenLabs voice from YOUR account (run list-voices). Omit to use .env or auto-pick premade.",
    ),
    no_captions: bool = typer.Option(False, "--no-captions"),
    regenerate_script: bool = typer.Option(
        False, "--regenerate-script", help="Force new OpenAI script (costs tokens)"
    ),
    regenerate_images: bool = typer.Option(
        False, "--regenerate-images", help="Regenerate all beat images"
    ),
    regenerate_voice: bool = typer.Option(
        False, "--regenerate-voice", help="Regenerate all section voiceovers"
    ),
    regenerate_assembly: bool = typer.Option(
        False, "--regenerate-assembly", help="Re-render final video even if it exists"
    ),
) -> None:
    """Generate ~2 min explainer. By default resumes from production/checkpoint.json."""
    if not campaign_dir.exists():
        typer.secho(f"Campaign folder not found: {campaign_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    settings = get_settings()
    settings.caption_mode = "keyword"
    settings.target_video_duration = 120.0
    if bg_music:
        settings.bg_music_path = bg_music
    settings.bg_music_volume = bg_music_volume
    if voice_id:
        settings.elevenlabs_voice_id = voice_id
    settings.enable_captions = not no_captions

    concept_def = load_concept(concept)
    typer.echo("Starting explainer production...")
    typer.echo(f"  Campaign : {campaign_dir}")
    typer.echo(f"  Concept  : {concept_def.title}")
    if settings.bg_music_path:
        typer.echo(f"  Bg music : {settings.bg_music_path}")

    try:
        result = run_explainer_production(
            campaign_dir=campaign_dir,
            concept_path=concept,
            settings=settings,
            skip_images=skip_images,
            skip_voice=skip_voice,
            skip_assembly=skip_assembly,
            regenerate_script=regenerate_script,
            regenerate_images=regenerate_images,
            regenerate_voice=regenerate_voice,
            regenerate_assembly=regenerate_assembly,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.secho("Explainer plan saved.", fg=typer.colors.GREEN)
    typer.echo(f"  Plan: {result['plan_path']}")
    typer.echo(f"  Checkpoint: {result['checkpoint_path']}")
    if result["image_paths"]:
        typer.echo(f"  Visuals: {len(result['image_paths'])} images")
    if result["narration_paths"]:
        typer.echo(f"  Voiceovers: {len(result['narration_paths'])} sections")
    if result["final_video"]:
        typer.secho(f"Final video: {result['final_video']}", fg=typer.colors.GREEN)


@app.command("manual-cut")
def manual_cut(
    video: Path = typer.Option(..., "--video", "-v"),
    start: str = typer.Option(..., "--start", "-s", help="Start time MM:SS or HH:MM:SS"),
    end: str = typer.Option(..., "--end", "-e", help="End time MM:SS or HH:MM:SS"),
    output: Path = typer.Option(..., "--output", "-o"),
) -> None:
    """Smoke-test ffmpeg clip extraction with manual timestamps."""
    from src.extractor.ffmpeg_clipper import extract_clip

    def parse_time(value: str) -> float:
        parts = [float(p) for p in value.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        raise typer.BadParameter("Time must be MM:SS or HH:MM:SS")

    start_sec = parse_time(start)
    end_sec = parse_time(end)
    extract_clip(video, output, start_sec, end_sec)
    typer.secho(f"Clip saved: {output}", fg=typer.colors.GREEN)


def _parse_clip_list(clips: str) -> list[str]:
    """Accept comma-separated clip names or a single filename."""
    return [part.strip() for part in clips.split(",") if part.strip()]


@app.command("produce")
def produce(
    run_dir: Path = typer.Option(
        ...,
        "--run-dir",
        "-r",
        help="Extraction output folder containing manifest.json and clips",
    ),
    topic: str = typer.Option(
        ...,
        "--topic",
        "-t",
        help="Video topic for script and images",
    ),
    clips: str = typer.Option(
        ...,
        "--clips",
        "-c",
        help='Clip filenames, comma-separated (e.g. "clip_04.mp4,clip_07.mp4")',
    ),
    target_duration: float = typer.Option(38.0, "--target-duration", help="Target video length (sec)"),
    clip_duration: float = typer.Option(9.0, "--clip-duration", help="Duration per clip segment (sec)"),
    skip_images: bool = typer.Option(False, "--skip-images", help="Skip image generation"),
    skip_voice: bool = typer.Option(False, "--skip-voice", help="Skip voiceover generation"),
    skip_assembly: bool = typer.Option(False, "--skip-assembly", help="Skip final video assembly"),
    bg_music: Path | None = typer.Option(
        None, "--bg-music", help="Background music file (trimmed to video length)"
    ),
    bg_music_volume: float = typer.Option(
        0.12, "--bg-music-volume", help="Background music volume 0.0-1.0 (default 0.12)"
    ),
    voice_id: str | None = typer.Option(
        None, "--voice-id", help="Override ElevenLabs voice ID from .env"
    ),
    no_captions: bool = typer.Option(False, "--no-captions", help="Disable burned-in captions"),
    regenerate_script: bool = typer.Option(
        False, "--regenerate-script", help="Regenerate script from match audio (ignore saved plan)"
    ),
) -> None:
    """Generate script, AI images, voiceover, and assemble final Short."""
    if not run_dir.exists():
        typer.secho(f"Run folder not found: {run_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    settings = get_settings()
    settings.target_video_duration = target_duration
    settings.clip_segment_duration = clip_duration
    settings.image_count = 3
    if bg_music:
        settings.bg_music_path = bg_music
    settings.bg_music_volume = bg_music_volume
    if voice_id:
        settings.elevenlabs_voice_id = voice_id
    settings.enable_captions = not no_captions

    clip_files = _parse_clip_list(clips)
    if len(clip_files) < 1:
        typer.secho("Provide at least 1 clip.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo("Starting production pipeline...")
    typer.echo(f"  Run folder : {run_dir}")
    typer.echo(f"  Topic      : {topic}")
    typer.echo(f"  Clips      : {', '.join(clip_files)}")
    typer.echo(f"  Target     : {target_duration}s (intro + {clip_duration}s per clip + 3 web images)")
    if settings.bg_music_path:
        typer.echo(f"  Bg music   : {settings.bg_music_path} (volume={bg_music_volume})")

    try:
        result = run_production(
            run_dir=run_dir,
            topic=topic,
            clip_files=clip_files,
            settings=settings,
            skip_images=skip_images,
            skip_voice=skip_voice,
            skip_assembly=skip_assembly,
            regenerate_script=regenerate_script,
        )
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    typer.secho("Production plan saved.", fg=typer.colors.GREEN)
    typer.echo(f"  Plan: {result['plan_path']}")

    if result["image_paths"]:
        typer.echo(f"  Images: {len(result['image_paths'])} generated")
    if result["narration_paths"]:
        typer.echo(f"  Voiceovers: {len(result['narration_paths'])} generated")
    if result["final_video"]:
        typer.secho(f"Final video: {result['final_video']}", fg=typer.colors.GREEN)


@app.command("list-voices")
def list_voices_cmd() -> None:
    """List premade/cloned voices on your ElevenLabs account (safe for free API)."""
    from src.generator.voice_generator import list_usable_voices

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        typer.secho("ELEVENLABS_API_KEY is not set in .env", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        voices = list_usable_voices(settings.elevenlabs_api_key)
    except Exception as exc:
        typer.secho(f"Failed to list voices: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    if not voices:
        typer.echo("No voices found on your account.")
        raise typer.Exit(0)

    typer.echo("Premade/cloned voices on YOUR account (use voice_id in .env):\n")
    for voice in voices:
        marker = " ← recommended" if voice["category"].lower() == "premade" else ""
        typer.echo(f"  {voice['name']}{marker}")
        typer.echo(f"    voice_id : {voice['voice_id']}")
        typer.echo(f"    category : {voice['category']}\n")
    typer.echo("Do not use library voice IDs from the web — they fail on free plans.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
