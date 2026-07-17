"""Local-first bridge from P68 pilot outputs into the portfolio review workspace."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_MEDIA = {".wav", ".mp3", ".m4a", ".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True, slots=True)
class ArtifactCandidate:
    kind: str
    label: str
    source: Path
    metadata: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pilot_workspace(pilot_dir: Path) -> dict[str, Any]:
    plan_path = pilot_dir / "content-plan.json"
    storyboard_path = pilot_dir / "storyboard.json"
    voice_path = pilot_dir / "voice-project.json"
    missing = [str(path) for path in (plan_path, storyboard_path, voice_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Pilot workspace is incomplete: {', '.join(missing)}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    voice = json.loads(voice_path.read_text(encoding="utf-8"))
    script = {
        "schema_version": "portfolio.script.v1",
        "text": plan.get("original_script") or voice.get("narration") or "",
        "hook": (plan.get("selected_concept") or {}).get("hook_direction"),
        "payoff": (plan.get("selected_concept") or {}).get("payoff_direction"),
        "source": str(plan_path),
    }
    scene_plan = {
        "schema_version": "portfolio.scene_plan.v1",
        "scenes": plan.get("shots") or storyboard,
        "storyboard": storyboard,
        "continuity_bible": plan.get("continuity_bible") or {},
        "source": str(storyboard_path),
    }
    voiceover = {
        "schema_version": "portfolio.voiceover.v1",
        "provider": "kokoro" if "kokoro" in json.dumps(voice).lower() else "local",
        "narration": voice.get("narration") or plan.get("original_script") or "",
        "style": (voice.get("brand") or {}).get("voiceStyle"),
        "duration_seconds": (voice.get("render") or {}).get("durationSeconds"),
        "source": str(voice_path),
    }
    return {"script": script, "scene_plan": scene_plan, "voiceover": voiceover}


def discover_artifacts(artifact_dir: Path, *, include_keyframes: bool = True) -> list[ArtifactCandidate]:
    candidates: list[ArtifactCandidate] = []
    narration = sorted((artifact_dir / "narration").glob("*")) if (artifact_dir / "narration").is_dir() else []
    narration_media = [path for path in narration if path.suffix.lower() in SUPPORTED_MEDIA]
    if narration_media:
        source = narration_media[-1]
        candidates.append(ArtifactCandidate("voiceover", "Kokoro narration", source, {"provider": "kokoro"}))

    preferred = [
        artifact_dir / "renders" / "hybrid-v1" / "final_review.mp4",
        artifact_dir / "renders" / "narrated-visual-v1" / "final_review.mp4",
        artifact_dir / "renders" / "review-v1" / "final_review.mp4",
        artifact_dir / "renders" / "visual-v1" / "final_review.mp4",
    ]
    preview = next((path for path in preferred if path.is_file()), None)
    if preview is None:
        renders = sorted((artifact_dir / "renders").glob("**/final_review.*")) if (artifact_dir / "renders").is_dir() else []
        preview = next((path for path in reversed(renders) if path.suffix.lower() in SUPPORTED_MEDIA), None)
    if preview:
        manifest_path = preview.parent / "render_manifest.json"
        metadata: dict[str, Any] = {"render_variant": preview.parent.name}
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata.update({
                "technical_pass": manifest.get("technical_pass"),
                "quality_approved": manifest.get("quality_approved"),
                "human_review_required": manifest.get("human_review_required", True),
                "probe": manifest.get("probe") or {},
            })
        candidates.append(ArtifactCandidate("preview", f"Free preview · {preview.parent.name}", preview, metadata))

    if include_keyframes:
        keyframe_root = artifact_dir / "generated-assets"
        if keyframe_root.is_dir():
            for path in sorted(keyframe_root.glob("*")):
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                    candidates.append(ArtifactCandidate("keyframe", f"Keyframe · {path.stem}", path, {}))
    return candidates


def safe_media_relative(*, brand_slug: str, content_id: str, pilot_id: str, candidate: ArtifactCandidate) -> Path:
    digest = sha256_file(candidate.source)
    safe_stem = "".join(char if char.isalnum() or char in "-_" else "-" for char in candidate.source.stem).strip("-")
    return Path(brand_slug) / content_id / pilot_id / f"{candidate.kind}-{safe_stem}-{digest[:12]}{candidate.source.suffix.lower()}"


def materialize_artifact(
    candidate: ArtifactCandidate, *, media_root: Path, relative: Path, dry_run: bool = False
) -> dict[str, Any]:
    if candidate.source.suffix.lower() not in SUPPORTED_MEDIA:
        raise ValueError(f"Unsupported review media: {candidate.source}")
    destination = (media_root.resolve() / relative).resolve()
    if media_root.resolve() not in destination.parents:
        raise ValueError("Artifact destination escapes PORTFOLIO_MEDIA_ROOT")
    digest = sha256_file(candidate.source)
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and sha256_file(destination) != digest:
            raise ValueError(f"Existing destination checksum mismatch: {destination}")
        if not destination.is_file():
            shutil.copy2(candidate.source, destination)
    mime_type = mimetypes.guess_type(candidate.source.name)[0] or "application/octet-stream"
    return {
        "kind": candidate.kind,
        "label": candidate.label,
        "local_locator": f"content://{relative.as_posix()}",
        "mime_type": mime_type,
        "sha256": digest,
        "size_bytes": candidate.source.stat().st_size,
        "metadata": {**candidate.metadata, "source_pipeline": "p68", "pilot_source": str(candidate.source)},
    }


def workspace_changed(current: dict[str, Any], desired: dict[str, Any]) -> bool:
    return any(current.get(key) != desired.get(key) for key in ("script", "scene_plan", "voiceover"))


def artifact_already_registered(existing: list[dict[str, Any]], payload: dict[str, Any]) -> bool:
    return any(
        item.get("kind") == payload["kind"] and item.get("sha256") == payload["sha256"]
        for item in existing
    )
