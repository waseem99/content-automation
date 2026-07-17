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
    EvidenceSource,
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
            confidence = _model_confidence(observation.get("confidence"))
            common = {
                "start_seconds": frame.timestamp_seconds,
                "confidence": confidence,
                "evidence": [frame.relative_path],
                "source_type": EvidenceSource.MODEL_OBSERVATION,
                "provider": f"{self.name}:{self.model}",
                "measured": False,
            }
            findings.append(
                AnalysisFinding(
                    id=f"shot-{frame.id}",
                    category="shot_taxonomy",
                    label=str(observation.get("shot_type") or "unclassified shot"),
                    summary=(
                        f"Subject: {observation.get('subject') or 'unknown'}; "
                        f"setting: {observation.get('setting') or 'unknown'}; "
                        f"style: {observation.get('visual_style') or 'unknown'}."
                    ),
                    **common,
                )
            )
            on_screen_text = observation.get("on_screen_text")
            if on_screen_text not in (None, "", [], {}):
                findings.append(
                    AnalysisFinding(
                        id=f"ocr-{frame.id}",
                        category="ocr",
                        label="on-screen text observation",
                        summary=(
                            on_screen_text
                            if isinstance(on_screen_text, str)
                            else json.dumps(on_screen_text, ensure_ascii=False)
                        ),
                        **common,
                    )
                )
            findings.append(
                AnalysisFinding(
                    id=f"emotion-{frame.id}",
                    category="emotional_beat",
                    label=str(observation.get("emotional_tone") or "uncertain emotion"),
                    summary="Frame-level emotional tone inferred by the local vision model.",
                    **common,
                )
            )
            findings.append(
                AnalysisFinding(
                    id=f"motion-{frame.id}",
                    category="motion",
                    label="motion clue",
                    summary=str(observation.get("motion_clues") or "No reliable motion clue."),
                    **common,
                )
            )
        return findings

    def analyze_sequence(
        self,
        workspace: Path,
        frames: list[FrameArtifact],
        transcript: list[TranscriptSegment],
        duration: float,
    ) -> tuple[list[dict[str, object]], list[AnalysisFinding], dict[str, object]]:
        """Analyze chronological visual evidence as a sequence instead of isolated images."""
        preferred = sorted(
            [frame for frame in frames if frame.preferred],
            key=lambda item: item.timestamp_seconds,
        )
        if len(preferred) > self.max_frames:
            step = (len(preferred) - 1) / max(self.max_frames - 1, 1)
            selected = [preferred[round(index * step)] for index in range(self.max_frames)]
        else:
            selected = preferred
        if not selected:
            return [], [], {}
        images = [
            base64.b64encode((workspace / frame.relative_path).read_bytes()).decode("ascii")
            for frame in selected
        ]
        timestamps = [round(frame.timestamp_seconds, 3) for frame in selected]
        transcript_text = "\n".join(
            f"[{segment.start_seconds:.2f}-{segment.end_seconds:.2f}] {segment.text}"
            for segment in transcript
        )[:10_000]
        prompt = (
            "Analyze these chronologically ordered frames and transcript as one short-form video. "
            "Return JSON with: story_arc (list of stage,start_seconds,end_seconds,summary), "
            "hook_mechanic, visual_progression, editing_patterns (list), emotional_progression, "
            "payoff, reusable_mechanics (list), and source_specific_elements_to_avoid (list). "
            "Describe mechanics for creating original work; never recommend copying exact shots, "
            "wording, branding, characters, music, or artwork. Frames occur at seconds: "
            f"{timestamps}. Video duration: {duration:.3f}. "
            f"Transcript:\n{transcript_text or '[unavailable]'}"
        )
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt, "images": images}],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw.get("message", {}).get("content", "{}")
            observation = json.loads(content) if isinstance(content, str) else content
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Local sequence model request failed: {exc}") from exc

        story_arc: list[dict[str, object]] = []
        for index, item in enumerate(observation.get("story_arc") or []):
            if not isinstance(item, dict):
                continue
            try:
                start = max(0.0, min(duration, float(item.get("start_seconds", 0))))
                end = max(start, min(duration, float(item.get("end_seconds", duration))))
            except (TypeError, ValueError):
                continue
            story_arc.append(
                {
                    "stage": str(item.get("stage") or f"beat_{index + 1}"),
                    "start_seconds": round(start, 3),
                    "end_seconds": round(end, 3),
                    "summary": str(item.get("summary") or "Sequence-level observed beat."),
                    "basis": "local multimodal sequence observation; confirm during human review",
                    "source_type": EvidenceSource.MODEL_OBSERVATION.value,
                    "confidence": _model_confidence(item.get("confidence")),
                }
            )
        common = {
            "start_seconds": 0,
            "end_seconds": duration,
            "confidence": _model_confidence(observation.get("confidence")),
            "evidence": [frame.relative_path for frame in selected],
            "source_type": EvidenceSource.MODEL_OBSERVATION,
            "provider": f"{self.name}:{self.model}:sequence",
            "measured": False,
        }
        findings = [
            AnalysisFinding(
                id="sequence-storytelling",
                category="storytelling",
                label=str(observation.get("hook_mechanic") or "sequence-level story observation"),
                summary=(
                    f"Visual progression: {observation.get('visual_progression') or 'uncertain'}. "
                    "Emotional progression: "
                    f"{observation.get('emotional_progression') or 'uncertain'}. "
                    f"Payoff: {observation.get('payoff') or 'uncertain'}."
                ),
                **common,
            ),
            AnalysisFinding(
                id="sequence-editing-patterns",
                category="editing_pattern",
                label="sequence-level editing mechanics",
                summary=json.dumps(observation.get("editing_patterns") or [], ensure_ascii=False),
                **common,
            ),
        ]
        summary = {
            "hook_mechanic": observation.get("hook_mechanic"),
            "visual_progression": observation.get("visual_progression"),
            "emotional_progression": observation.get("emotional_progression"),
            "payoff": observation.get("payoff"),
            "reusable_mechanics": observation.get("reusable_mechanics") or [],
            "source_specific_elements_to_avoid": (
                observation.get("source_specific_elements_to_avoid") or []
            ),
            "evidence_timestamps": timestamps,
        }
        return story_arc, findings, summary


def _model_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.65
    return round(min(0.95, max(0.35, confidence)), 3)


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
            "source_type": EvidenceSource.DETERMINISTIC_FALLBACK.value,
            "confidence": 0.35,
        }
        for name, start, end in sections
    ]


def _multimodal_fallback_findings(
    *,
    duration: float,
    metadata: MediaMetadata,
    scenes: list[SceneArtifact],
    transcript: list[TranscriptSegment],
    transcript_metrics: dict[str, object],
) -> list[AnalysisFinding]:
    findings: list[AnalysisFinding] = []
    if transcript:
        findings.append(
            AnalysisFinding(
                id="caption-rhythm",
                category="caption_rhythm",
                label="spoken phrase rhythm",
                summary=(
                    f"{transcript_metrics['caption_phrase_count']} phrases at "
                    f"{transcript_metrics['words_per_minute']} words per minute; average "
                    f"phrase length {transcript_metrics['average_caption_phrase_words']} words."
                ),
                start_seconds=transcript[0].start_seconds,
                end_seconds=transcript[-1].end_seconds,
                confidence=0.75,
                evidence=["transcript/transcript.json", "transcript/word_timestamps.json"],
                source_type=EvidenceSource.MODEL_OBSERVATION,
                provider="local-transcription",
            )
        )
        emotional_text = " ".join(segment.text.lower() for segment in transcript)
        if any(term in emotional_text for term in ("but", "until", "suddenly", "surprise", "why")):
            label = "curiosity-to-reveal"
        elif "?" in emotional_text:
            label = "question-led curiosity"
        else:
            label = "neutral information progression"
        findings.append(
            AnalysisFinding(
                id="emotional-progression-fallback",
                category="emotional_beat",
                label=label,
                summary="Heuristic emotional progression derived from locally transcribed wording.",
                start_seconds=0,
                end_seconds=duration,
                confidence=0.4,
                evidence=["transcript/transcript.json"],
                source_type=EvidenceSource.DETERMINISTIC_FALLBACK,
                provider="transcript-keyword-heuristic:v1",
            )
        )
    else:
        findings.append(
            AnalysisFinding(
                id="caption-rhythm-unavailable",
                category="caption_rhythm",
                label="transcript unavailable",
                summary="Caption rhythm cannot be inferred until local transcription succeeds.",
                confidence=1,
                source_type=EvidenceSource.DETERMINISTIC_FALLBACK,
                provider="missing-transcript-fallback",
            )
        )

    if metadata.silence_intervals:
        findings.append(
            AnalysisFinding(
                id="measured-audio-cues",
                category="audio_cue",
                label="silence and pause pattern",
                summary=f"Detected {len(metadata.silence_intervals)} measured silence intervals.",
                start_seconds=0,
                end_seconds=duration,
                confidence=0.95,
                evidence=["media/media_metadata.json"],
                source_type=EvidenceSource.MEASURED,
                provider="ffmpeg-metadata",
                measured=True,
            )
        )
    else:
        findings.append(
            AnalysisFinding(
                id="audio-cues-fallback",
                category="audio_cue",
                label="speech-density proxy",
                summary=(
                    "No measured silence intervals are available; speech density is retained "
                    "as a weak timing proxy, not as music or SFX recognition."
                ),
                start_seconds=0,
                end_seconds=duration,
                confidence=0.3,
                evidence=["transcript/transcript.json"] if transcript else [],
                source_type=EvidenceSource.DETERMINISTIC_FALLBACK,
                provider="speech-density-fallback:v1",
            )
        )

    findings.append(
        AnalysisFinding(
            id="shot-rhythm-measured",
            category="editing",
            label="measured shot rhythm",
            summary=f"{len(scenes)} detected scenes provide cut timing but not shot-size labels.",
            confidence=0.95 if scenes else 0.5,
            evidence=["frames/frame_manifest.json"],
            source_type=EvidenceSource.MEASURED,
            provider="pyscenedetect" if scenes else "duration-fallback",
            measured=True,
        )
    )
    return findings


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
            source_type=EvidenceSource.MEASURED,
            provider="ffprobe",
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
            source_type=EvidenceSource.MEASURED,
            provider="frame-extractor",
            measured=True,
        ),
    ]
    findings.extend(
        _multimodal_fallback_findings(
            duration=duration,
            metadata=metadata,
            scenes=scenes,
            transcript=transcript,
            transcript_metrics=transcript_metrics,
        )
    )
    fallback_reasons: list[str] = []
    if not transcript:
        fallback_reasons.append("local transcription returned no segments")
    if not metadata.silence_intervals:
        fallback_reasons.append("measured silence intervals are unavailable")
    analyzer_name = "rule-based-fallback"
    analyzer_version = "1"
    sequence_summary: dict[str, object] = {}
    observed_story_arc: list[dict[str, object]] = []
    if visual_provider is not None:
        try:
            findings.extend(visual_provider.analyze_frames(workspace, frames))
            sequence_analyzer = getattr(visual_provider, "analyze_sequence", None)
            if callable(sequence_analyzer):
                observed_story_arc, sequence_findings, sequence_summary = sequence_analyzer(
                    workspace, frames, transcript, duration
                )
                findings.extend(sequence_findings)
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
                    source_type=EvidenceSource.MEASURED,
                    provider=visual_provider.name,
                    measured=True,
                )
            )
            fallback_reasons.append("local visual provider failed")
    else:
        fallback_reasons.append("local visual provider was not enabled")

    if not any(finding.category == "ocr" for finding in findings):
        findings.append(
            AnalysisFinding(
                id="ocr-unavailable",
                category="ocr",
                label="on-screen text unavailable",
                summary="No reliable OCR observation is available; do not infer source captions.",
                confidence=1,
                source_type=EvidenceSource.DETERMINISTIC_FALLBACK,
                provider="missing-ocr-fallback",
            )
        )
        fallback_reasons.append("no reliable OCR observation was produced")
    if not any(finding.category == "shot_taxonomy" for finding in findings):
        findings.append(
            AnalysisFinding(
                id="shot-taxonomy-unavailable",
                category="shot_taxonomy",
                label="shot size unclassified",
                summary=(
                    "Cut timing is measured, but close-up/wide/POV taxonomy requires visual "
                    "model output or human review."
                ),
                confidence=1,
                evidence=["frames/frame_manifest.json"],
                source_type=EvidenceSource.DETERMINISTIC_FALLBACK,
                provider="missing-vision-fallback",
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
    evidence_summary = {
        source.value: sum(1 for finding in findings if finding.source_type == source)
        for source in EvidenceSource
    }
    audio_cues = [
        {
            "label": finding.label,
            "summary": finding.summary,
            "source_type": finding.source_type.value,
            "confidence": finding.confidence,
        }
        for finding in findings
        if finding.category == "audio_cue"
    ]

    return ReferenceAnalysis(
        hook={
            "first_visual_seconds": 0.0,
            "first_spoken_line_seconds": first_spoken,
            "first_detected_change_seconds": first_scene_change,
            "curiosity_or_conflict_visible_seconds": hook_visible_at,
            "hook_type": "immediate-visual" if hook_visible_at <= 1 else "delayed-context",
            "human_review_required": True,
        },
        story_arc=observed_story_arc or _story_arc(duration),
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
                [
                    finding
                    for finding in findings
                    if finding.source_type == EvidenceSource.MODEL_OBSERVATION
                    and finding.category in {"shot_taxonomy", "ocr", "emotional_beat", "motion"}
                ]
            ),
            "shot_taxonomy": [
                finding.label for finding in findings if finding.category == "shot_taxonomy"
            ],
            "ocr_observation_count": len(
                [finding for finding in findings if finding.category == "ocr" and finding.evidence]
            ),
            "human_style_classification_required": True,
            "sequence_storytelling": sequence_summary,
        },
        audio_language={**transcript_metrics, "audio_cues": audio_cues},
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
                evidence=[
                    f"{len(scenes)} detected scenes",
                    f"{len(preferred_frames)} usable frames",
                ],
            ),
            "originality_risk": ObjectiveScore(
                score=originality_risk,
                evidence=["source-specific wording and visual composition must be excluded"],
            ),
        },
        analyzer={"name": analyzer_name, "version": analyzer_version},
        evidence_summary=evidence_summary,
        fallback_reasons=sorted(set(fallback_reasons)),
    )
