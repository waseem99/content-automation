from __future__ import annotations

from pathlib import Path

from refintel.analysis import analyze_reference
from refintel.models import (
    AnalysisFinding,
    EvidenceSource,
    FrameArtifact,
    MediaMetadata,
    SceneArtifact,
    TranscriptSegment,
)


class FixtureVisionProvider:
    name = "fixture-local-vision"
    version = "1"

    def analyze_frames(
        self,
        workspace: Path,
        frames: list[FrameArtifact],
    ) -> list[AnalysisFinding]:
        return [
            AnalysisFinding(
                id="fixture-shot",
                category="shot_taxonomy",
                label="close-up",
                summary="A local model observed a close-up.",
                start_seconds=frames[0].timestamp_seconds,
                confidence=0.72,
                evidence=[frames[0].relative_path],
                source_type=EvidenceSource.MODEL_OBSERVATION,
                provider=self.name,
            ),
            AnalysisFinding(
                id="fixture-ocr",
                category="ocr",
                label="on-screen text observation",
                summary="WHY DOES IT DO THIS?",
                start_seconds=frames[0].timestamp_seconds,
                confidence=0.68,
                evidence=[frames[0].relative_path],
                source_type=EvidenceSource.MODEL_OBSERVATION,
                provider=self.name,
            ),
        ]


def fixture_inputs() -> dict[str, object]:
    return {
        "metadata": MediaMetadata(
            duration_seconds=30,
            width=1080,
            height=1920,
            fps=30,
            orientation="portrait",
            silence_intervals=[(6.2, 6.8)],
        ),
        "frames": [
            FrameArtifact(
                id="frame-1",
                timestamp_seconds=1,
                relative_path="frames/interval/frame-1.jpg",
                kind="interval",
            )
        ],
        "scenes": [
            SceneArtifact(
                id="scene-1",
                start_seconds=0,
                end_seconds=6,
                detector="fixture",
            ),
            SceneArtifact(
                id="scene-2",
                start_seconds=6,
                end_seconds=12,
                detector="fixture",
            ),
        ],
        "transcript": [
            TranscriptSegment(
                id="segment-1",
                start_seconds=0.4,
                end_seconds=2.4,
                text="Why does this happen?",
            ),
            TranscriptSegment(
                id="segment-2",
                start_seconds=18,
                end_seconds=21,
                text="But the surprising answer is movement.",
            ),
        ],
    }


def test_multimodal_analysis_labels_measured_model_and_fallback_evidence(
    tmp_path: Path,
) -> None:
    analysis = analyze_reference(
        workspace=tmp_path,
        visual_provider=FixtureVisionProvider(),
        **fixture_inputs(),
    )

    sources = {finding.source_type for finding in analysis.findings}
    assert sources == {
        EvidenceSource.MEASURED,
        EvidenceSource.MODEL_OBSERVATION,
        EvidenceSource.DETERMINISTIC_FALLBACK,
    }
    assert analysis.evidence_summary == {
        "measured": 4,
        "model_observation": 3,
        "deterministic_fallback": 1,
    }
    assert all(finding.human_review_required for finding in analysis.findings)
    assert any(finding.category == "ocr" and finding.evidence for finding in analysis.findings)
    assert "close-up" in analysis.visual_language["shot_taxonomy"]
    assert analysis.audio_language["audio_cues"][0]["source_type"] == "measured"
    assert all(stage["source_type"] == "deterministic_fallback" for stage in analysis.story_arc)


def test_fallback_mode_never_claims_ocr_or_shot_taxonomy_observations(tmp_path: Path) -> None:
    inputs = fixture_inputs()
    inputs["transcript"] = []
    inputs["metadata"] = MediaMetadata(
        duration_seconds=30,
        width=1080,
        height=1920,
        fps=30,
        orientation="portrait",
    )
    analysis = analyze_reference(
        workspace=tmp_path,
        visual_provider=None,
        **inputs,
    )

    ocr = next(finding for finding in analysis.findings if finding.category == "ocr")
    taxonomy = next(
        finding for finding in analysis.findings if finding.category == "shot_taxonomy"
    )
    assert ocr.source_type == EvidenceSource.DETERMINISTIC_FALLBACK
    assert not ocr.evidence
    assert taxonomy.label == "shot size unclassified"
    assert "local visual provider was not enabled" in analysis.fallback_reasons
    assert "local transcription returned no segments" in analysis.fallback_reasons
    assert analysis.human_review_required is True
