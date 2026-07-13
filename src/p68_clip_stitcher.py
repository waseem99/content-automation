"""Provider-neutral P68 clip normalization and natural assembly.

Generated or approved clips enter through a manifest. FFmpeg normalizes and
stitches them in planned order, mixes continuous audio, burns optional captions,
and writes a review-only render manifest. It never calls a generation provider,
approves quality/rights, uploads, or publishes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


P68_RENDER_VERSION = "p68.clip_assembly.v1"
ALLOWED_RIGHTS = {"owned", "generated_for_project", "licensed", "approved_internal"}
ALLOWED_TRANSITIONS = {"cold_open", "direct_cut", "action_cut", "match_cut", "j_cut", "l_cut", "crossfade"}
MAX_CROSSFADE_SECONDS = 0.3


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required binary is unavailable: {name}")
    return path


def _run(command: list[str], *, timeout: int = 1800) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()[-4000:]
        raise RuntimeError(f"Media command failed: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_media(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    ffprobe = _require_binary("ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {target}: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    video = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), {})
    audio = next((item for item in payload.get("streams", []) if item.get("codec_type") == "audio"), {})
    rate = str(video.get("avg_frame_rate") or "0/1").split("/")
    fps = float(rate[0]) / max(float(rate[1]), 1) if len(rate) == 2 else 0.0
    return {
        "duration_seconds": round(float(payload.get("format", {}).get("duration") or 0), 3),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": round(fps, 3),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "has_audio": bool(audio),
        "sample_rate": int(audio.get("sample_rate") or 0),
    }


def validate_clip_manifest(plan: dict[str, Any], clip_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    planned = [shot.get("shot_id") for shot in plan.get("shots") or []]
    clips = clip_manifest.get("clips") or []
    supplied = [clip.get("shot_id") for clip in clips]
    if supplied != planned:
        errors.append("clip_order_must_exactly_match_planned_shot_order")
    if len(set(supplied)) != len(supplied):
        errors.append("duplicate_shot_id")
    for clip in clips:
        shot_id = clip.get("shot_id") or "unknown"
        path = Path(str(clip.get("path") or ""))
        if not path.is_file():
            errors.append(f"{shot_id}:clip_file_missing")
        if clip.get("rights_status") not in ALLOWED_RIGHTS:
            errors.append(f"{shot_id}:rights_status_not_accepted")
        if not str(clip.get("provider") or "").strip():
            errors.append(f"{shot_id}:provider_lineage_required")
        if not str(clip.get("prompt_or_asset_reference") or "").strip():
            errors.append(f"{shot_id}:prompt_or_asset_reference_required")
        if clip.get("human_review_status") not in {"approved_for_assembly", "pending_final_review"}:
            errors.append(f"{shot_id}:human_review_status_required")
    return sorted(set(errors))


def transition_schedule(plan: dict[str, Any]) -> list[dict[str, Any]]:
    schedule = []
    for shot in plan.get("shots") or []:
        transition = shot.get("transition_in") or {}
        strategy = transition.get("strategy") or "direct_cut"
        if strategy not in ALLOWED_TRANSITIONS:
            raise ValueError(f"Unsupported transition strategy: {strategy}")
        crossfade = float(transition.get("duration_seconds") or 0)
        if strategy == "crossfade" and not 0 < crossfade <= MAX_CROSSFADE_SECONDS:
            raise ValueError("Crossfades must be greater than 0 and no longer than 300 ms")
        if strategy != "crossfade":
            crossfade = 0.0
        if strategy == "j_cut":
            audio_timing = "incoming narration or ambience may lead the picture cut by up to 180 ms"
        elif strategy == "l_cut":
            audio_timing = "outgoing narration or ambience may trail the picture cut by up to 180 ms"
        else:
            audio_timing = "continuous master narration/music/ambience bridges the picture cut"
        schedule.append(
            {
                "shot_id": shot.get("shot_id"),
                "visual_transition": strategy,
                "crossfade_seconds": crossfade,
                "audio_bridge": audio_timing,
                "story_motivated": True,
            }
        )
    return schedule


def normalize_clip(
    source: str | Path,
    target: str | Path,
    *,
    duration_seconds: float,
    handle_seconds: float = 0.5,
) -> dict[str, Any]:
    source_path, target_path = Path(source), Path(target)
    source_probe = probe_media(source_path)
    required = duration_seconds + handle_seconds
    if source_probe["duration_seconds"] + 0.05 < required:
        raise ValueError(
            f"Clip {source_path} is too short for {duration_seconds:.3f}s plus "
            f"{handle_seconds:.3f}s transition handle"
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _require_binary("ffmpeg")
    trim_start = handle_seconds / 2
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,format=yuv420p,setsar=1"
    )
    command = [ffmpeg, "-y", "-ss", f"{trim_start:.3f}", "-i", str(source_path)]
    if source_probe["has_audio"]:
        command += ["-map", "0:v:0", "-map", "0:a:0", "-af", "aresample=48000"]
    else:
        command += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    command += [
        "-vf",
        video_filter,
        "-t",
        f"{duration_seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-shortest",
        str(target_path),
    ]
    _run(command)
    normalized_probe = probe_media(target_path)
    if (normalized_probe["width"], normalized_probe["height"]) != (1080, 1920):
        raise RuntimeError("Normalized clip is not 1080x1920")
    if abs(normalized_probe["fps"] - 30) > 0.05:
        raise RuntimeError("Normalized clip is not 30 fps")
    return normalized_probe


def _concat_clips(clips: list[Path], target: Path) -> None:
    ffmpeg = _require_binary("ffmpeg")
    list_path = target.with_suffix(".concat.txt")
    list_path.write_text(
        "\n".join(f"file '{path.resolve().as_posix().replace(chr(39), chr(39) * 2)}'" for path in clips),
        encoding="utf-8",
    )
    try:
        _run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(target),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)


def _escape_subtitle_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def finish_master(
    stitched_path: Path,
    output_path: Path,
    *,
    narration_path: Path | None = None,
    music_path: Path | None = None,
    sfx_paths: list[Path] | None = None,
    captions_path: Path | None = None,
) -> None:
    ffmpeg = _require_binary("ffmpeg")
    command = [ffmpeg, "-y", "-i", str(stitched_path)]
    audio_labels = ["[0:a]volume=0.28[clipaudio]"]
    mix_inputs = ["[clipaudio]"]
    input_index = 1
    for path, volume, label in (
        (narration_path, 1.0, "narration"),
        (music_path, 0.16, "music"),
    ):
        if path:
            command += ["-i", str(path)]
            audio_labels.append(f"[{input_index}:a]aresample=48000,volume={volume}[{label}]")
            mix_inputs.append(f"[{label}]")
            input_index += 1
    for index, path in enumerate(sfx_paths or []):
        command += ["-i", str(path)]
        label = f"sfx{index}"
        audio_labels.append(f"[{input_index}:a]aresample=48000,volume=0.55[{label}]")
        mix_inputs.append(f"[{label}]")
        input_index += 1
    audio_labels.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0,"
        "loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
    )
    command += ["-filter_complex", ";".join(audio_labels), "-map", "0:v:0", "-map", "[aout]"]
    if captions_path:
        command += ["-vf", f"subtitles='{_escape_subtitle_path(captions_path)}'"]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_path),
    ]
    _run(command)


def assemble_clip_plan(
    plan: dict[str, Any],
    clip_manifest: dict[str, Any],
    output_dir: str | Path,
    *,
    narration_path: str | Path | None = None,
    music_path: str | Path | None = None,
    sfx_paths: list[str | Path] | None = None,
    captions_path: str | Path | None = None,
) -> dict[str, Any]:
    errors = validate_clip_manifest(plan, clip_manifest)
    if errors:
        return {"schema_version": P68_RENDER_VERSION, "is_valid": False, "errors": errors}
    output_root = Path(output_dir)
    normalized_dir = output_root / "normalized_clips"
    output_root.mkdir(parents=True, exist_ok=True)
    shots = plan["shots"]
    clips_by_id = {clip["shot_id"]: clip for clip in clip_manifest["clips"]}
    normalized: list[Path] = []
    normalized_records = []
    for shot in shots:
        clip = clips_by_id[shot["shot_id"]]
        target = normalized_dir / f"{shot['shot_id']}.mp4"
        probe = normalize_clip(
            clip["path"],
            target,
            duration_seconds=float(shot["duration_seconds"]),
            handle_seconds=float(shot.get("transition_handle_seconds") or 0.5),
        )
        normalized.append(target)
        normalized_records.append(
            {
                "shot_id": shot["shot_id"],
                "source_path": str(clip["path"]),
                "normalized_path": str(target),
                "source_sha256": sha256_file(Path(clip["path"])),
                "provider": clip["provider"],
                "rights_status": clip["rights_status"],
                "probe": probe,
            }
        )
    stitched = output_root / "picture_lock.mp4"
    final = output_root / "final_review.mp4"
    _concat_clips(normalized, stitched)
    finish_master(
        stitched,
        final,
        narration_path=Path(narration_path) if narration_path else None,
        music_path=Path(music_path) if music_path else None,
        sfx_paths=[Path(path) for path in (sfx_paths or [])],
        captions_path=Path(captions_path) if captions_path else None,
    )
    final_probe = probe_media(final)
    expected_duration = sum(float(shot["duration_seconds"]) for shot in shots)
    technical_pass = (
        final_probe["width"] == 1080
        and final_probe["height"] == 1920
        and abs(final_probe["fps"] - 30) <= 0.05
        and final_probe["video_codec"] == "h264"
        and final_probe["audio_codec"] == "aac"
        and abs(final_probe["duration_seconds"] - expected_duration) <= 0.35
    )
    manifest = {
        "schema_version": P68_RENDER_VERSION,
        "is_valid": technical_pass,
        "plan_schema_version": plan.get("schema_version"),
        "shot_order": [shot["shot_id"] for shot in shots],
        "normalized_clips": normalized_records,
        "transition_schedule": transition_schedule(plan),
        "audio": {
            "narration": str(narration_path) if narration_path else None,
            "music": str(music_path) if music_path else None,
            "sfx": [str(path) for path in (sfx_paths or [])],
            "captions": str(captions_path) if captions_path else None,
            "target_loudness_lufs": -14,
            "true_peak_db": -1.5,
        },
        "output_path": str(final),
        "output_sha256": sha256_file(final),
        "probe": final_probe,
        "technical_pass": technical_pass,
        "quality_approved": False,
        "render_approved": False,
        "publish_allowed": False,
        "human_review_required": True,
        "blocking_reviews": [
            "natural continuity and stitching",
            "narration and audio finish",
            "caption readability",
            "facts, rights, originality, advertiser suitability, and monetization",
        ],
    }
    manifest_path = output_root / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
