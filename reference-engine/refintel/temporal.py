from __future__ import annotations

import hashlib
import json
import math
import statistics
import wave
from array import array
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, select_autoescape
from pydantic import BaseModel, ConfigDict, Field

from .acquisition import sha256_path
from .images import EvidenceKind as ImageEvidenceKind
from .images import extract_ocr
from .models import ReferenceProject, TranscriptSegment


class TemporalStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    REUSED = "reused"


class TemporalEvidenceKind(StrEnum):
    MEASURED = "measured"
    EXTRACTED = "extracted"
    MODEL_OBSERVATION = "model_observation"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    UNAVAILABLE = "unavailable"


class AudioEnergyPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    rms: float = Field(ge=0, le=1)
    relative_energy: float = Field(ge=0, le=1)
    silence_candidate: bool
    peak_candidate: bool


class AudioTimeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    source_type: TemporalEvidenceKind
    provider: str
    duration_seconds: float = Field(ge=0)
    mean_rms: float = Field(ge=0, le=1)
    dynamic_range: float = Field(ge=0, le=1)
    silence_ratio: float = Field(ge=0, le=1)
    peak_count: int = Field(ge=0)
    points: list[AudioEnergyPoint] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FrameOCRCue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_seconds: float = Field(ge=0)
    frame_path: str
    status: str
    source_type: TemporalEvidenceKind
    text: str = ""
    confidence: float | None = Field(default=None, ge=0, le=1)
    text_coverage: float = Field(default=0, ge=0, le=1)
    cta_candidate: bool = False


class TemporalWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    role_candidate: str
    mean_motion: float = Field(ge=0, le=1)
    peak_motion: float = Field(ge=0, le=1)
    static_ratio: float = Field(ge=0, le=1)
    mean_brightness: float | None = Field(default=None, ge=0, le=1)
    candidate_cut_count: int = Field(ge=0)
    spoken_word_count: int = Field(ge=0)
    caption_segment_count: int = Field(ge=0)
    audio_mean_energy: float | None = Field(default=None, ge=0, le=1)
    audio_peak_count: int = Field(ge=0)
    ocr_cue_count: int = Field(ge=0)
    model_observation_count: int = Field(ge=0)
    evidence: list[str] = Field(default_factory=list)


class ProductionDifficulty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    tier: str
    evidence: list[str]
    source_type: TemporalEvidenceKind = TemporalEvidenceKind.DETERMINISTIC_FALLBACK
    human_review_required: bool = True


class TemporalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "p75.temporal_report.v1"
    reference_id: str
    title: str
    status: TemporalStatus
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_digest: str
    duration_seconds: float = Field(ge=0)
    window_seconds: float = Field(gt=0)
    windows: list[TemporalWindow]
    audio: AudioTimeline
    ocr_cues: list[FrameOCRCue]
    hook: dict[str, Any]
    story_map: list[dict[str, Any]]
    editing_profile: dict[str, Any]
    caption_profile: dict[str, Any]
    engagement_mechanics: list[dict[str, Any]]
    payoff_and_cta: dict[str, Any]
    motion_disclosure: dict[str, Any]
    production_difficulty: ProductionDifficulty
    evidence_coverage: dict[str, int]
    limitations: list[str]
    rights_declaration: str
    human_review_required: bool = True
    source_text_must_not_be_reused_verbatim: bool = True
    source_media_must_not_enter_generated_content: bool = True
    automatic_generation: bool = False
    automatic_publication: bool = False


def _input_digest(workspace: Path, project: ReferenceProject) -> str:
    digest = hashlib.sha256()
    digest.update(project.reference_id.encode("utf-8"))
    digest.update(project.access.declaration.value.encode("utf-8"))
    for relative in (
        "analysis/reference_analysis.json",
        "frames/every_frame_metrics.json",
        "frames/frame_manifest.json",
        "transcript/transcript.json",
        "transcript/word_timestamps.json",
        "media/audio.wav",
    ):
        path = workspace / relative
        digest.update(relative.encode("utf-8"))
        digest.update(sha256_path(path).encode("ascii") if path.is_file() else b"missing")
    return digest.hexdigest()


def analyze_audio_timeline(audio_path: Path, *, window_seconds: float = 0.5) -> AudioTimeline:
    if not audio_path.is_file() or audio_path.stat().st_size <= 44:
        return AudioTimeline(
            status="unavailable",
            source_type=TemporalEvidenceKind.UNAVAILABLE,
            provider="missing-audio",
            duration_seconds=0,
            mean_rms=0,
            dynamic_range=0,
            silence_ratio=0,
            peak_count=0,
            limitations=["Normalized PCM audio is unavailable."],
        )
    try:
        handle = wave.open(str(audio_path), "rb")
    except (wave.Error, OSError):
        return AudioTimeline(
            status="unavailable",
            source_type=TemporalEvidenceKind.UNAVAILABLE,
            provider="invalid-wave",
            duration_seconds=0,
            mean_rms=0,
            dynamic_range=0,
            silence_ratio=0,
            peak_count=0,
            limitations=["Audio could not be decoded as normalized PCM WAV."],
        )
    with handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        if sample_width != 2 or sample_rate <= 0:
            return AudioTimeline(
                status="unavailable",
                source_type=TemporalEvidenceKind.UNAVAILABLE,
                provider="unsupported-wave-format",
                duration_seconds=(frame_count / sample_rate if sample_rate else 0),
                mean_rms=0,
                dynamic_range=0,
                silence_ratio=0,
                peak_count=0,
                limitations=["Audio energy requires 16-bit normalized PCM WAV."],
            )
        frames_per_window = max(1, round(sample_rate * window_seconds))
        raw_points: list[tuple[float, float, float]] = []
        start = 0.0
        while chunk := handle.readframes(frames_per_window):
            samples = array("h")
            samples.frombytes(chunk)
            if not samples:
                break
            if channels > 1:
                mono = [
                    sum(samples[offset : offset + channels]) / channels
                    for offset in range(0, len(samples), channels)
                ]
            else:
                mono = samples
            rms = math.sqrt(sum(float(value) ** 2 for value in mono) / len(mono)) / 32768
            end = min(frame_count / sample_rate, start + len(mono) / sample_rate)
            raw_points.append((start, end, min(1.0, rms)))
            start = end
    values = [item[2] for item in raw_points]
    if not values:
        return AudioTimeline(
            status="unavailable",
            source_type=TemporalEvidenceKind.UNAVAILABLE,
            provider="empty-wave",
            duration_seconds=0,
            mean_rms=0,
            dynamic_range=0,
            silence_ratio=0,
            peak_count=0,
            limitations=["Audio contained no measurable samples."],
        )
    median = statistics.median(values)
    deviation = statistics.median(abs(value - median) for value in values)
    silence_threshold = max(0.003, median * 0.12)
    peak_threshold = min(1.0, max(median * 1.8, median + 3 * deviation))
    maximum = max(values)
    points = [
        AudioEnergyPoint(
            start_seconds=round(start, 4),
            end_seconds=round(end, 4),
            rms=round(value, 6),
            relative_energy=round(value / maximum, 5) if maximum else 0,
            silence_candidate=value <= silence_threshold,
            peak_candidate=value >= peak_threshold and value > silence_threshold,
        )
        for start, end, value in raw_points
    ]
    return AudioTimeline(
        status="succeeded",
        source_type=TemporalEvidenceKind.MEASURED,
        provider="pcm-rms:v1",
        duration_seconds=round(raw_points[-1][1], 4),
        mean_rms=round(statistics.mean(values), 6),
        dynamic_range=round(max(values) - min(values), 6),
        silence_ratio=round(sum(item.silence_candidate for item in points) / len(points), 5),
        peak_count=sum(item.peak_candidate for item in points),
        points=points,
    )


def _load_every_frame(workspace: Path) -> dict[str, Any]:
    path = workspace / "frames" / "every_frame_metrics.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _ocr_cues(project: ReferenceProject, workspace: Path, limit: int = 20) -> list[FrameOCRCue]:
    frames = sorted(
        [frame for frame in project.frames if frame.preferred],
        key=lambda frame: frame.timestamp_seconds,
    )
    if len(frames) > limit:
        step = (len(frames) - 1) / max(1, limit - 1)
        frames = [frames[round(index * step)] for index in range(limit)]
    cues: list[FrameOCRCue] = []
    for frame in frames:
        path = workspace / frame.relative_path
        try:
            result = extract_ocr(path)
            source_type = (
                TemporalEvidenceKind.EXTRACTED
                if result.source_type == ImageEvidenceKind.EXTRACTED
                else TemporalEvidenceKind.UNAVAILABLE
            )
            cues.append(
                FrameOCRCue(
                    timestamp_seconds=frame.timestamp_seconds,
                    frame_path=frame.relative_path,
                    status=result.status,
                    source_type=source_type,
                    text=result.text,
                    confidence=result.mean_confidence,
                    text_coverage=result.text_coverage,
                    cta_candidate=result.cta_candidate,
                )
            )
        except Exception as exc:  # noqa: BLE001 - isolate OCR per frame
            cues.append(
                FrameOCRCue(
                    timestamp_seconds=frame.timestamp_seconds,
                    frame_path=frame.relative_path,
                    status=f"failed:{type(exc).__name__}",
                    source_type=TemporalEvidenceKind.UNAVAILABLE,
                )
            )
    return cues


def _word_count(segments: list[TranscriptSegment]) -> int:
    return sum(len(segment.words) or len(segment.text.split()) for segment in segments)


def _overlaps(start: float, end: float, item_start: float, item_end: float) -> bool:
    return item_start < end and item_end > start


def _window_role(index: int, count: int) -> str:
    if index == 0:
        return "hook_candidate"
    if index == 1:
        return "setup_candidate"
    if index == count - 1:
        return "payoff_or_cta_candidate"
    return "development"


def _window_size(duration: float) -> float:
    if duration <= 30:
        return 2.0
    if duration <= 90:
        return 5.0
    if duration <= 300:
        return 10.0
    return 30.0


def _build_windows(
    project: ReferenceProject,
    *,
    duration: float,
    every_frame: dict[str, Any],
    audio: AudioTimeline,
    ocr_cues: list[FrameOCRCue],
) -> tuple[list[TemporalWindow], float]:
    seconds = _window_size(duration)
    count = max(1, math.ceil(duration / seconds))
    frame_metrics = every_frame.get("frames") or []
    cuts = every_frame.get("candidate_cuts") or []
    if not cuts:
        cuts = [
            {"timestamp_seconds": scene.start_seconds, "change_score": scene.confidence}
            for scene in project.scenes
            if scene.start_seconds > 0
        ]
    findings = project.analysis.findings if project.analysis else []
    windows: list[TemporalWindow] = []
    for zero_index in range(count):
        start = zero_index * seconds
        end = min(duration, start + seconds)
        measured = [
            item
            for item in frame_metrics
            if start <= float(item.get("timestamp_seconds", -1)) < end
        ]
        motion = [min(1.0, max(0.0, float(item.get("change_score", 0)))) for item in measured]
        brightness = [min(1.0, max(0.0, float(item.get("brightness", 0)))) for item in measured]
        segments = [
            segment
            for segment in project.transcript
            if _overlaps(start, end, segment.start_seconds, segment.end_seconds)
        ]
        audio_points = [
            point
            for point in audio.points
            if _overlaps(start, end, point.start_seconds, point.end_seconds)
        ]
        ocr = [cue for cue in ocr_cues if start <= cue.timestamp_seconds < end]
        observations = [
            finding
            for finding in findings
            if finding.source_type.value == "model_observation"
            and start <= float(finding.start_seconds or 0) < end
        ]
        window_cuts = [
            item for item in cuts if start <= float(item.get("timestamp_seconds", -1)) < end
        ]
        evidence = []
        if measured:
            evidence.append("frames/every_frame_metrics.json")
        if window_cuts:
            evidence.append("frames/every_frame_metrics.json or scene boundaries")
        if segments:
            evidence.append("transcript/transcript.json")
        if audio_points:
            evidence.append("media/audio.wav")
        if ocr:
            evidence.extend(sorted({cue.frame_path for cue in ocr}))
        windows.append(
            TemporalWindow(
                index=zero_index + 1,
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                role_candidate=_window_role(zero_index, count),
                mean_motion=round(statistics.mean(motion), 5) if motion else 0,
                peak_motion=round(max(motion), 5) if motion else 0,
                static_ratio=(
                    round(sum(value < 0.003 for value in motion) / len(motion), 5)
                    if motion
                    else 1.0
                ),
                mean_brightness=(round(statistics.mean(brightness), 5) if brightness else None),
                candidate_cut_count=len(window_cuts),
                spoken_word_count=_word_count(segments),
                caption_segment_count=len(segments),
                audio_mean_energy=(
                    round(statistics.mean(point.relative_energy for point in audio_points), 5)
                    if audio_points
                    else None
                ),
                audio_peak_count=sum(point.peak_candidate for point in audio_points),
                ocr_cue_count=sum(cue.status == "succeeded" and bool(cue.text) for cue in ocr),
                model_observation_count=len(observations),
                evidence=evidence,
            )
        )
    return windows, seconds


def _mechanics(
    project: ReferenceProject,
    windows: list[TemporalWindow],
    ocr_cues: list[FrameOCRCue],
) -> list[dict[str, Any]]:
    mechanics: list[dict[str, Any]] = []
    first = windows[0]
    if first.candidate_cut_count or first.peak_motion >= 0.08:
        mechanics.append(
            {
                "label": "early visual change candidate",
                "source_type": "measured",
                "confidence": 0.85,
                "evidence": [f"window 0–{first.end_seconds:.1f}s"],
            }
        )
    if project.transcript and project.transcript[0].start_seconds <= 1.5:
        mechanics.append(
            {
                "label": "early narration entry",
                "source_type": "extracted",
                "confidence": 0.9,
                "evidence": [f"first speech at {project.transcript[0].start_seconds:.2f}s"],
            }
        )
    if any("?" in segment.text for segment in project.transcript):
        mechanics.append(
            {
                "label": "question-led curiosity candidate",
                "source_type": "extracted",
                "confidence": 0.7,
                "evidence": ["question punctuation in local transcript"],
            }
        )
    if any(cue.cta_candidate for cue in ocr_cues):
        mechanics.append(
            {
                "label": "on-screen CTA candidate",
                "source_type": "extracted",
                "confidence": 0.75,
                "evidence": [
                    f"frame at {cue.timestamp_seconds:.2f}s"
                    for cue in ocr_cues
                    if cue.cta_candidate
                ],
            }
        )
    return mechanics


def _difficulty(
    duration: float,
    windows: list[TemporalWindow],
    audio: AudioTimeline,
    ocr_cues: list[FrameOCRCue],
) -> ProductionDifficulty:
    cuts = sum(window.candidate_cut_count for window in windows)
    captions = sum(window.caption_segment_count for window in windows)
    motion_windows = sum(window.mean_motion >= 0.02 for window in windows)
    score = min(
        100,
        round(
            20
            + min(30, cuts / max(duration / 60, 1 / 60) * 1.5)
            + min(20, captions * 1.5)
            + min(15, motion_windows * 2)
            + min(10, audio.peak_count)
            + min(5, sum(bool(cue.text) for cue in ocr_cues)),
        ),
    )
    tier = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return ProductionDifficulty(
        score=score,
        tier=tier,
        evidence=[
            f"{cuts} candidate cuts",
            f"{captions} caption/transcript segments",
            f"{motion_windows} motion-active windows",
            f"{audio.peak_count} measured audio peaks",
        ],
    )


def _render_html(report: TemporalReport, target: Path) -> None:
    template = Environment(
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
    ).from_string(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ report.title }} — Temporal Evidence</title>
  <style>
    :root { font-family: Inter, system-ui, sans-serif; color: #f5f6f8; background: #0b0d12; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    .shell { max-width: 1400px; margin: auto; padding: 24px; }
    .card { background: #151821; border: 1px solid #2a2f3a; border-radius: 15px;
      padding: 16px; margin: 14px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px; }
    .kicker { color: #ffcf33; text-transform: uppercase; letter-spacing: .1em;
      font-size: 12px; }
    .muted { color: #a7adbb; }
    .warning { border-left: 4px solid #ffcf33; background: #211e12; padding: 12px; }
    .window { border-left: 5px solid #ffcf33; background: #10131a; padding: 12px;
      border-radius: 8px; }
    .bar { height: 8px; background: #282e3b; border-radius: 5px; overflow: hidden; }
    .bar i { display: block; height: 100%; background: #ffcf33; }
    pre { white-space: pre-wrap; word-break: break-word; }
    video { width: 100%; max-height: 60vh; background: #000; border-radius: 10px; }
    @media(max-width: 700px) { .shell { padding: 12px; } }
  </style>
</head>
<body>
<main class="shell">
  <div class="kicker">P75 Temporal evidence · multimodal timeline</div>
  <h1>{{ report.title }}</h1>
  <p class="muted">
    {{ report.duration_seconds }}s · {{ report.status }} · human review required
  </p>
  <div class="warning">
    This report identifies abstract mechanics for original production. Never reuse source
    footage, wording, voices, music, branding, or composition without permission.
  </div>
  <section class="card">
    <video controls preload="metadata" src="../media/analysis.mp4"></video>
  </section>
  <section class="grid">
    <div class="card"><h2>Motion disclosure</h2><pre>{{ motion }}</pre></div>
    <div class="card"><h2>Hook evidence</h2><pre>{{ hook }}</pre></div>
    <div class="card"><h2>Editing profile</h2><pre>{{ editing }}</pre></div>
    <div class="card"><h2>Production difficulty</h2><pre>{{ difficulty }}</pre></div>
  </section>
  <section class="card">
    <h2>Chronological evidence windows</h2>
    <div class="grid">
    {% for window in report.windows %}
      <article class="window">
        <strong>
          {{ window.start_seconds }}–{{ window.end_seconds }}s · {{ window.role_candidate }}
        </strong>
        <p>
          cuts {{ window.candidate_cut_count }} · words {{ window.spoken_word_count }} ·
          OCR {{ window.ocr_cue_count }} · audio peaks {{ window.audio_peak_count }}
        </p>
        <div class="bar"><i style="width:{{ window.mean_motion * 100 }}%"></i></div>
        <p class="muted">
          mean motion {{ window.mean_motion }} · static {{ window.static_ratio }}
        </p>
      </article>
    {% endfor %}
    </div>
  </section>
  <section class="grid">
    <div class="card"><h2>Story map</h2><pre>{{ story }}</pre></div>
    <div class="card"><h2>Engagement candidates</h2><pre>{{ mechanics }}</pre></div>
    <div class="card"><h2>Payoff and CTA</h2><pre>{{ payoff }}</pre></div>
    <div class="card"><h2>Limitations</h2><pre>{{ limitations }}</pre></div>
  </section>
</main>
</body>
</html>"""
    )
    rendered = template.render(
        report=report.model_dump(mode="json"),
        motion=json.dumps(report.motion_disclosure, indent=2),
        hook=json.dumps(report.hook, indent=2),
        editing=json.dumps(report.editing_profile, indent=2),
        difficulty=report.production_difficulty.model_dump_json(indent=2),
        story=json.dumps(report.story_map, indent=2),
        mechanics=json.dumps(report.engagement_mechanics, indent=2),
        payoff=json.dumps(report.payoff_and_cta, indent=2),
        limitations=json.dumps(report.limitations, indent=2),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")


def build_temporal_report(
    project: ReferenceProject,
    workspace: Path,
    *,
    force: bool = False,
) -> tuple[TemporalReport, Path, Path]:
    if not project.media or not project.analysis:
        raise ValueError("Video media and reference analysis are required")
    target = workspace / "analysis" / "temporal_report.json"
    html_target = workspace / "reports" / "temporal.html"
    digest = _input_digest(workspace, project)
    if target.is_file() and not force:
        previous = TemporalReport.model_validate_json(target.read_text(encoding="utf-8"))
        if previous.input_digest == digest:
            reused = previous.model_copy(
                update={"status": TemporalStatus.REUSED, "generated_at": datetime.now(UTC)}
            )
            target.write_text(reused.model_dump_json(indent=2), encoding="utf-8")
            _render_html(reused, html_target)
            return reused, target, html_target

    duration = max(0.001, project.media.duration_seconds)
    every_frame = _load_every_frame(workspace)
    audio = analyze_audio_timeline(workspace / "media" / "audio.wav")
    ocr_cues = _ocr_cues(project, workspace)
    windows, window_seconds = _build_windows(
        project,
        duration=duration,
        every_frame=every_frame,
        audio=audio,
        ocr_cues=ocr_cues,
    )
    cuts = every_frame.get("candidate_cuts") or []
    cut_times = [float(item.get("timestamp_seconds", 0)) for item in cuts]
    if not cut_times:
        cut_times = [scene.start_seconds for scene in project.scenes if scene.start_seconds > 0]
    first_change = min(cut_times) if cut_times else None
    first_speech = project.transcript[0].start_seconds if project.transcript else None
    overall_static = (
        float(every_frame.get("static_frame_ratio"))
        if every_frame.get("static_frame_ratio") is not None
        else statistics.mean(window.static_ratio for window in windows)
    )
    mean_motion = (
        float(every_frame.get("mean_change_score"))
        if every_frame.get("mean_change_score") is not None
        else statistics.mean(window.mean_motion for window in windows)
    )
    motion_class = (
        "still_or_slideshow_like"
        if overall_static >= 0.9
        else "low_motion"
        if overall_static >= 0.7
        else "moderate_motion"
        if mean_motion < 0.08
        else "high_motion"
    )
    scene_count = len(project.scenes) or len(cut_times)
    cuts_per_minute = round(scene_count / max(duration / 60, 1 / 60), 2)
    shot_lengths = [max(0, scene.end_seconds - scene.start_seconds) for scene in project.scenes]
    transcript_metrics = project.analysis.pacing
    cta_segments = transcript_metrics.get("cta_candidates") or []
    model_payoff = project.analysis.visual_language.get("sequence_storytelling", {}).get("payoff")
    limitations: list[str] = []
    if not every_frame:
        limitations.append(
            "Every-frame metrics are unavailable; motion uses sparse frames and scene boundaries."
        )
    if audio.status != "succeeded":
        limitations.extend(audio.limitations)
    if not project.transcript:
        limitations.append("Transcript and caption timing are unavailable.")
    if not any(cue.status == "succeeded" and cue.text for cue in ocr_cues):
        limitations.append("No reliable deterministic frame OCR text was extracted.")
    if not model_payoff:
        limitations.append("Payoff intent is unconfirmed without sequence-level model evidence.")
    status = TemporalStatus.PARTIAL if limitations else TemporalStatus.SUCCEEDED
    model_observations = sum(
        finding.source_type.value == "model_observation" for finding in project.analysis.findings
    )
    report = TemporalReport(
        reference_id=project.reference_id,
        title=project.source.title,
        status=status,
        input_digest=digest,
        duration_seconds=round(duration, 3),
        window_seconds=window_seconds,
        windows=windows,
        audio=audio,
        ocr_cues=ocr_cues,
        hook={
            "first_candidate_change_seconds": first_change,
            "first_spoken_line_seconds": first_speech,
            "first_window_peak_motion": windows[0].peak_motion,
            "classification": (
                "immediate_evidence_candidate"
                if (first_change is not None and first_change <= 1.5)
                or (first_speech is not None and first_speech <= 1.5)
                else "delayed_or_unconfirmed"
            ),
            "source_type": "measured_and_extracted",
            "human_review_required": True,
        },
        story_map=[dict(item) for item in project.analysis.story_arc],
        editing_profile={
            "candidate_cut_count": scene_count,
            "cuts_per_minute": cuts_per_minute,
            "average_shot_seconds": (
                round(statistics.mean(shot_lengths), 3) if shot_lengths else None
            ),
            "mean_frame_change": round(mean_motion, 5),
            "static_frame_ratio": round(overall_static, 5),
            "source_type": "measured" if every_frame else "deterministic_fallback",
        },
        caption_profile={
            "segment_count": len(project.transcript),
            "word_count": _word_count(project.transcript),
            "words_per_minute": transcript_metrics.get("words_per_minute", 0),
            "first_spoken_line_seconds": first_speech,
            "speech_density": transcript_metrics.get("speech_density", 0),
            "source_type": "extracted" if project.transcript else "unavailable",
        },
        engagement_mechanics=_mechanics(project, windows, ocr_cues),
        payoff_and_cta={
            "payoff_observation": model_payoff,
            "payoff_source_type": ("model_observation" if model_payoff else "unavailable"),
            "transcript_cta_candidates": cta_segments,
            "ocr_cta_timestamps": [cue.timestamp_seconds for cue in ocr_cues if cue.cta_candidate],
            "human_review_required": True,
        },
        motion_disclosure={
            "classification": motion_class,
            "static_frame_ratio": round(overall_static, 5),
            "mean_frame_change": round(mean_motion, 5),
            "is_actual_motion_confirmed": bool(every_frame) and overall_static < 0.9,
            "still_image_or_slideshow_warning": overall_static >= 0.9,
            "source_type": "measured" if every_frame else "deterministic_fallback",
        },
        production_difficulty=_difficulty(duration, windows, audio, ocr_cues),
        evidence_coverage={
            "measured_frame_samples": len(every_frame.get("frames") or []),
            "candidate_cuts": scene_count,
            "transcript_segments": len(project.transcript),
            "audio_windows": len(audio.points),
            "ocr_frames": len(ocr_cues),
            "model_observations": model_observations,
        },
        limitations=limitations,
        rights_declaration=project.access.declaration.value,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _render_html(report, html_target)
    return report, target, html_target
