from __future__ import annotations

import json
import math
import wave
from pathlib import Path

import pytest
from PIL import Image

from refintel.images import EvidenceKind, OCRResult
from refintel.models import (
    FrameArtifact,
    MediaMetadata,
    Platform,
    ProjectStatus,
    ReferenceAnalysis,
    ReferenceProject,
    RightsDeclaration,
    SceneArtifact,
    SourceAccess,
    SourceDescriptor,
    TranscriptSegment,
)
from refintel.temporal import (
    TemporalStatus,
    analyze_audio_timeline,
    build_temporal_report,
)


def write_wave(path: Path, *, duration: float = 4.0, sample_rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = []
    for index in range(round(duration * sample_rate)):
        second = index / sample_rate
        amplitude = 0 if second < 1 else 2500 if second < 3 else 14000
        samples.append(round(amplitude * math.sin(2 * math.pi * 220 * second)))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(value.to_bytes(2, "little", signed=True) for value in samples))


def fixture_project(workspace: Path, *, with_transcript: bool = True) -> ReferenceProject:
    frame_dir = workspace / "frames" / "interval"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp in enumerate((0.0, 1.0, 2.0, 3.0)):
        target = frame_dir / f"frame-{index}.jpg"
        Image.new("RGB", (360, 640), (30 + index * 40, 60, 90)).save(target)
        frames.append(
            FrameArtifact(
                id=f"frame-{index}",
                timestamp_seconds=timestamp,
                relative_path=str(target.relative_to(workspace)),
                kind="interval",
            )
        )
    transcript = (
        [
            TranscriptSegment(
                id="segment-1",
                start_seconds=0.4,
                end_seconds=1.4,
                text="Why does this happen?",
            ),
            TranscriptSegment(
                id="segment-2",
                start_seconds=2.5,
                end_seconds=3.7,
                text="Follow for the next explanation.",
            ),
        ]
        if with_transcript
        else []
    )
    analysis = ReferenceAnalysis(
        hook={"hook_type": "immediate-visual"},
        story_arc=[
            {
                "stage": "hook",
                "start_seconds": 0,
                "end_seconds": 1,
                "basis": "fixture model observation",
                "source_type": "model_observation",
                "confidence": 0.8,
            },
            {
                "stage": "payoff",
                "start_seconds": 3,
                "end_seconds": 4,
                "basis": "fixture model observation",
                "source_type": "model_observation",
                "confidence": 0.8,
            },
        ],
        pacing={
            "words_per_minute": 90,
            "speech_density": 0.55,
            "cta_candidates": [{"start_seconds": 2.5, "end_seconds": 3.7, "text": "Follow"}],
        },
        visual_language={"sequence_storytelling": {"payoff": "A final explanation is observed."}},
        findings=[],
    )
    project = ReferenceProject(
        reference_id="ref-temporal-fixture",
        status=ProjectStatus.PROCESSING,
        source=SourceDescriptor(
            kind="file",
            platform=Platform.LOCAL,
            original_path="fixture.mp4",
            title="Temporal fixture",
            canonical_key="sha256:fixture",
        ),
        access=SourceAccess(declaration=RightsDeclaration.PUBLIC_INTERNAL_RESEARCH),
        workspace_path=str(workspace),
        media=MediaMetadata(
            duration_seconds=4,
            width=360,
            height=640,
            fps=10,
            orientation="portrait",
        ),
        frames=frames,
        scenes=[
            SceneArtifact(
                id="scene-1",
                start_seconds=0,
                end_seconds=2,
                detector="fixture",
            ),
            SceneArtifact(
                id="scene-2",
                start_seconds=2,
                end_seconds=4,
                detector="fixture",
            ),
        ],
        transcript=transcript,
        analysis=analysis,
    )
    (workspace / "analysis").mkdir(parents=True, exist_ok=True)
    (workspace / "analysis" / "reference_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    (workspace / "transcript").mkdir(parents=True, exist_ok=True)
    (workspace / "transcript" / "transcript.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in transcript]), encoding="utf-8"
    )
    return project


def write_every_frame(workspace: Path, *, static: bool = False) -> None:
    frames = []
    for index in range(40):
        change = 0.0005 if static else (0.18 if index in {10, 20, 30} else 0.012)
        frames.append(
            {
                "frame": index,
                "timestamp_seconds": index / 10,
                "change_score": change,
                "brightness": 0.4 + index / 200,
            }
        )
    payload = {
        "schema_version": "p74.every_frame_metrics.v1",
        "static_frame_ratio": 0.98 if static else 0.1,
        "mean_change_score": 0.0005 if static else 0.0246,
        "frames": frames,
        "candidate_cuts": (
            []
            if static
            else [
                {"timestamp_seconds": 1.0, "change_score": 0.18},
                {"timestamp_seconds": 2.0, "change_score": 0.18},
                {"timestamp_seconds": 3.0, "change_score": 0.18},
            ]
        ),
    }
    target = workspace / "frames" / "every_frame_metrics.json"
    target.write_text(json.dumps(payload), encoding="utf-8")


def fixture_ocr(_path: Path) -> OCRResult:
    return OCRResult(
        status="succeeded",
        provider="fixture-ocr",
        source_type=EvidenceKind.EXTRACTED,
        text="Follow for more",
        mean_confidence=0.9,
        text_coverage=0.08,
        cta_candidate=True,
        cta_evidence=["follow"],
    )


def test_audio_timeline_measures_energy_silence_and_peaks(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    write_wave(audio)
    result = analyze_audio_timeline(audio)
    assert result.status == "succeeded"
    assert result.source_type.value == "measured"
    assert result.points
    assert result.silence_ratio > 0
    assert result.peak_count > 0
    assert result.dynamic_range > 0


def test_temporal_report_combines_modalities_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "reference"
    project = fixture_project(workspace)
    write_every_frame(workspace)
    write_wave(workspace / "media" / "audio.wav")
    monkeypatch.setattr("refintel.temporal.extract_ocr", fixture_ocr)

    first, manifest_path, html_path = build_temporal_report(project, workspace)
    second, _, _ = build_temporal_report(project, workspace)

    assert first.status == TemporalStatus.SUCCEEDED
    assert second.status == TemporalStatus.REUSED
    assert first.motion_disclosure["classification"] == "moderate_motion"
    assert first.motion_disclosure["is_actual_motion_confirmed"] is True
    assert first.evidence_coverage["measured_frame_samples"] == 40
    assert first.evidence_coverage["audio_windows"] > 0
    assert first.windows[0].spoken_word_count > 0
    assert first.engagement_mechanics
    assert first.payoff_and_cta["payoff_source_type"] == "model_observation"
    assert first.production_difficulty.human_review_required is True
    assert first.source_media_must_not_enter_generated_content is True
    assert first.source_text_must_not_be_reused_verbatim is True
    assert first.automatic_publication is False
    assert manifest_path.is_file()
    assert html_path.is_file()
    assert "Temporal evidence" in html_path.read_text(encoding="utf-8")


def test_temporal_report_discloses_still_or_slideshow_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "reference"
    project = fixture_project(workspace)
    write_every_frame(workspace, static=True)
    write_wave(workspace / "media" / "audio.wav")
    monkeypatch.setattr("refintel.temporal.extract_ocr", fixture_ocr)

    report, _, _ = build_temporal_report(project, workspace)
    assert report.motion_disclosure["classification"] == "still_or_slideshow_like"
    assert report.motion_disclosure["still_image_or_slideshow_warning"] is True
    assert report.motion_disclosure["is_actual_motion_confirmed"] is False


def test_missing_modalities_are_partial_and_never_claim_motion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "reference"
    project = fixture_project(workspace, with_transcript=False)

    def missing_ocr(_path: Path) -> OCRResult:
        return OCRResult(
            status="unavailable",
            provider="missing",
            source_type=EvidenceKind.UNAVAILABLE,
        )

    monkeypatch.setattr("refintel.temporal.extract_ocr", missing_ocr)
    project.analysis.visual_language = {}
    (workspace / "analysis" / "reference_analysis.json").write_text(
        project.analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    report, _, _ = build_temporal_report(project, workspace)
    assert report.status == TemporalStatus.PARTIAL
    assert report.motion_disclosure["is_actual_motion_confirmed"] is False
    assert report.motion_disclosure["source_type"] == "deterministic_fallback"
    assert report.audio.status == "unavailable"
    assert report.limitations


def test_frame_ocr_failure_is_isolated_per_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "reference"
    project = fixture_project(workspace)
    write_every_frame(workspace)
    write_wave(workspace / "media" / "audio.wav")
    calls = 0

    def flaky_ocr(path: Path) -> OCRResult:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("fixture OCR failure")
        return fixture_ocr(path)

    monkeypatch.setattr("refintel.temporal.extract_ocr", flaky_ocr)
    report, _, _ = build_temporal_report(project, workspace)
    assert len(report.ocr_cues) == 4
    assert sum(cue.status.startswith("failed:") for cue in report.ocr_cues) == 1
    assert sum(cue.status == "succeeded" for cue in report.ocr_cues) == 3
