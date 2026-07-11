from __future__ import annotations

import base64
import json
import statistics
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from .models import (
    AnalysisFinding,
    FrameArtifact,
    MediaMetadata,
    ObjectiveScore,
    ReferenceAnalysis,
    SceneArtifact,
    TranscriptSegment,
)
from .transcript import analyze_transcript


class VisualAnalysisProvider(Protocol):
    name: str
    version: str

    def analyze_frames(
        self,
        workspace: Path,
        frames: list[FrameArtifact],
    ) -> list[AnalysisFinding]: ...


class OllamaVisionProvider:
    name = "ollama-vision"
    version = "v1"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        max_frames: int = 12,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.max_frames = max_frames

    def analyze_frames(
        self,
        workspace: Path,
        frames: list[FrameArtifact],
    ) -> list[AnalysisFinding]:
        selected = sorted(
            [frame for frame in frames if frame.preferred],
            key=lambda item: item.quality_score,
            reverse=True,
        )[: self.max_frames]
        findings: list[AnalysisFinding] = []
        for frame in sorted(selected, key=lambda item: item.timestamp_seconds):
            image_path = workspace / frame.relative_path
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            payload = {
                "model": self.model,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Analyze this video frame for internal reference research. "
                            "Return JSON with subject, setting, shot_type, on_screen_text, "
                            "visual_style, motion_clues, emotional_tone, and safety_notes. "
                            "Do not identify private people."
                        ),
                        "images": [encoded],
                    }
                ],
            }
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                content = raw.get("message", {}).get("content", "{}")
                observation = json.loads(content) if isinstance(content, str) else content
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(f"Local visual model request failed: {exc}") from exc
            findings.append(
                AnalysisFinding(
                    id=f"vision-{frame.id}",
                    category="visual",
                    label=str(observation.get("shot_type") or "frame observation"),
                    summary=json.dumps(observation, ensure_ascii=False),
                    start_seconds=frame.timestamp_seconds,
                    confidence=0.65,
                    evidence=[frame.relative_path],
                    measured=False,
                )
            )
        return findings


def _story_arc(duration: float) -> list[dict[str, object]]:
    duration = max(duration, 1.0)
    sections = (
        ("hook", 0.00, 0.08),
        ("setup", 0.08, 0.24),
        ("escalation", 0.24, 0.58),
        ("peak", 0.58, 0.74),
        ("reveal", 0.74, 0.90),
        ("resolution_or_cta", 0.90, 1.00),
    )
    return [
        {
            "stage": name,
            "start_seconds": round(duration * start, 3),
            "end_seconds": round(duration * end, 3),
            "basis": "duration-proportional fallback; confirm during human review",
        }
        for name, start, end in sections
    ]


def analyze_reference(
    *,
    workspace: Path,
    metadata: MediaMetadata,
    frames: list[FrameArtifact],
    scenes: list[SceneArtifact],
    transcript: list[TranscriptSegment],
    visual_provider: VisualAnalysisProvider | None = None,
) -> ReferenceAnalysis:
    duration = max(metadata.duration_seconds, 0.001)
    scene_lengths = [max(0.0, scene.end_seconds - scene.start_seconds) for scene in scenes]
    preferred_frames = [frame for frame in frames if frame.preferred]
    transcript_metrics = analyze_transcript(transcript, duration_seconds=duration)
    first_scene_change = scenes[1].start_seconds if len(scenes) > 1 else None
    first_spoken = transcript_metrics.get("first_spoken_line_seconds")
    hook_visible_at = min(
        [value for value in (first_scene_change, first_spoken, 0.0) if value is not None]
    )

    findings: list[AnalysisFinding] = [
        AnalysisFinding(
            id="measured-duration",
            category="technical",
            label="duration",
            summary=f"The reference is {duration:.2f} seconds long.",
            start_seconds=0,
            confidence=1,
            evidence=["media/media_metadata.json"],
            measured=True,
        ),
        AnalysisFinding(
            id="measured-frame-rate",
            category="editing",
            label="visual evidence density",
            summary=(
                f"{len(preferred_frames)} preferred frames and {len(scenes)} detected scenes "
                "are available for analysis."
            ),
            confidence=1,
            evidence=["frames/frame_manifest.json"],
            measured=True,
        ),
    ]
    analyzer_name = "rule-based-fallback"
    analyzer_version = "1"
    if visual_provider is not None:
        try:
            findings.extend(visual_provider.analyze_frames(workspace, frames))
            analyzer_name = visual_provider.name
            analyzer_version = visual_provider.version
        except RuntimeError as exc:
            findings.append(
                AnalysisFinding(
                    id="visual-provider-warning",
                    category="system",
                    label="visual provider unavailable",
                    summary=str(exc),
                    confidence=1,
                    evidence=[],
                    measured=True,
                )
            )

    average_shot = round(statistics.mean(scene_lengths), 3) if scene_lengths else duration
    visual_change_rate = round(len(scenes) / max(duration / 60, 1 / 60), 2)
    caption_rate = round(len(transcript) / max(duration / 60, 1 / 60), 2)
    hook_speed_score = 100 if hook_visible_at <= 1 else max(10, int(100 - hook_visible_at * 15))
    pacing_score = min(100, int(45 + min(40, visual_change_rate * 2) + min(15, caption_rate / 3)))
    evidence_count = len(preferred_frames) + len(transcript) + len(scenes)
    engagement = min(100, int((hook_speed_score * 0.45) + (pacing_score * 0.55)))
    rights_safety = 65 if evidence_count else 40
    monetization = min(100, int(50 + engagement * 0.35))
    originality_risk = 45 if visual_provider else 30

    return ReferenceAnalysis(
        hook={
            "first_visual_seconds": 0.0,
            "first_spoken_line_seconds": first_spoken,
            "first_detected_change_seconds": first_scene_change,
            "curiosity_or_conflict_visible_seconds": hook_visible_at,
            "hook_type": "immediate-visual" if hook_visible_at <= 1 else "delayed-context",
            "human_review_required": True,
        },
        story_arc=_story_arc(duration),
        pacing={
            "duration_seconds": round(duration, 3),
            "scene_count": len(scenes),
            "average_shot_seconds": average_shot,
            "visual_changes_per_minute": visual_change_rate,
            "caption_changes_per_minute": caption_rate,
            "preferred_frame_count": len(preferred_frames),
            **transcript_metrics,
        },
        visual_language={
            "orientation": metadata.orientation,
            "resolution": [metadata.width, metadata.height],
            "provider_observation_count": len(
                [finding for finding in findings if finding.category == "visual"]
            ),
            "human_style_classification_required": True,
        },
        audio_language=transcript_metrics,
        findings=findings,
        objective_scores={
            "engagement": ObjectiveScore(
                score=engagement,
                evidence=[
                    f"hook established at {hook_visible_at:.2f}s",
                    f"visual changes per minute: {visual_change_rate}",
                    f"caption changes per minute: {caption_rate}",
                ],
            ),
            "rights_and_safety": ObjectiveScore(
                score=rights_safety,
                evidence=[
                    "rights declaration recorded",
                    "source media remains in the local reference workspace",
                    "human review required before reuse",
                ],
            ),
            "advertiser_suitability": ObjectiveScore(
                score=70,
                evidence=["automated score is provisional until sensitive imagery is reviewed"],
            ),
            "monetization": ObjectiveScore(
                score=monetization,
                evidence=["derived from measured hook speed and pacing density"],
            ),
            "production_difficulty": ObjectiveScore(
                score=min(100, int(25 + len(scenes) * 2 + len(preferred_frames))),
                evidence=[f"{len(scenes)} detected scenes", f"{len(preferred_frames)} usable frames"],
            ),
            "originality_risk": ObjectiveScore(
                score=originality_risk,
                evidence=["source-specific wording and visual composition must be excluded"],
            ),
        },
        analyzer={"name": analyzer_name, "version": analyzer_version},
    )
