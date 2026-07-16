from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from refintel.comparison import (
    ComparisonStatus,
    GateDecision,
    ReferenceProfile,
    build_comparison_library,
    evaluate_originality_text,
    load_comparison_metadata,
)
from refintel.models import ObjectiveScore, Platform, ReferenceFingerprint


def write_reference(
    root: Path,
    reference_id: str,
    *,
    title: str,
    platform: Platform = Platform.FACEBOOK,
    rights: str | None = "public-internal-research",
    hook_type: str = "curiosity",
    visual_rate: float = 24,
    mechanics: list[str] | None = None,
    transcript: str | None = None,
) -> Path:
    workspace = root / reference_id
    exports = workspace / "exports"
    exports.mkdir(parents=True)
    fingerprint = ReferenceFingerprint(
        reference_id=reference_id,
        title=title,
        platform=platform,
        duration_seconds=45,
        hook={"hook_type": hook_type},
        story_arc=[
            {"stage": "setup", "start_seconds": 0, "end_seconds": 8},
            {"stage": "development", "start_seconds": 8, "end_seconds": 35},
            {"stage": "payoff", "start_seconds": 35, "end_seconds": 45},
        ],
        pacing={
            "visual_changes_per_minute": visual_rate,
            "caption_changes_per_minute": 18,
            "average_shot_seconds": 2.5,
        },
        visual_language={
            "shot_grammar": "Close-up camera motion followed by wide shot and reveal",
            "sequence_storytelling": {
                "reusable_mechanics": ["Escalation followed by payoff"],
            },
        },
        audio_language={"delivery": "Narration with a music build and sound effect"},
        objective_scores={"engagement": ObjectiveScore(score=80)},
        reusable_mechanics=mechanics
        or [
            "Use a curiosity hook in the first second.",
            "Use fast cuts with readable captions.",
            "Place the CTA after the payoff.",
        ],
        source_specific_elements_to_exclude=[
            "exact source story",
            "source presenter identity",
        ],
        evidence_timestamps=[0, 8, 35, 45],
        generated_at=datetime(2026, 7, 16, tzinfo=UTC),
    )
    fingerprint_path = exports / "reference_fingerprint.json"
    fingerprint_path.write_text(fingerprint.model_dump_json(indent=2), encoding="utf-8")
    project = {
        "reference_id": reference_id,
        "access": {"declaration": rights} if rights else {},
        "media": {"orientation": "portrait", "duration_seconds": 45},
    }
    (workspace / "project.json").write_text(json.dumps(project), encoding="utf-8")
    if transcript is not None:
        transcript_dir = workspace / "transcript"
        transcript_dir.mkdir()
        (transcript_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    return fingerprint_path


def source_set(tmp_path: Path) -> list[Path]:
    return [
        write_reference(
            tmp_path,
            "ref-alpha",
            title="Reference Alpha",
            transcript=(
                "A rescued fox follows an unfamiliar trail before safely returning to the forest."
            ),
        ),
        write_reference(
            tmp_path,
            "ref-beta",
            title="Reference Beta",
            platform=Platform.YOUTUBE,
            visual_rate=25,
            transcript=(
                "Researchers uncover how elephants detect distant movement through the ground."
            ),
        ),
        write_reference(
            tmp_path,
            "ref-gamma",
            title="Reference Gamma",
            platform=Platform.TIKTOK,
            rights="permitted",
            visual_rate=23,
            transcript=("A coastal bird changes its hunting route when the evening tide arrives."),
        ),
    ]


def test_comparison_builds_clusters_patterns_brief_and_gates(tmp_path: Path) -> None:
    paths = source_set(tmp_path / "references")
    metadata = {
        "ref-alpha": {"brand_id": "animal-x", "format_name": "vertical_short"},
        "ref-beta": {"brand_id": "animal-x", "format_name": "vertical_short"},
        "ref-gamma": {"brand_id": "rawr", "format_name": "vertical_short"},
    }
    report, report_path, html_path = build_comparison_library(
        paths,
        tmp_path / "comparison",
        metadata=metadata,
        brand_id="animal-x",
        target_format="facebook_reel",
        topic="How desert animals conserve water",
    )

    assert report.status == ComparisonStatus.SUCCEEDED
    assert report.reference_count == 3
    assert len(report.pairwise) == 3
    alpha_beta = next(
        item
        for item in report.pairwise
        if {item.left_reference_id, item.right_reference_id} == {"ref-alpha", "ref-beta"}
    )
    assert alpha_beta.brand_similarity == 1
    assert alpha_beta.format_similarity == 1
    assert alpha_beta.platform_similarity == 0
    assert report.clusters
    assert report.patterns
    assert all(not pattern.source_specific_expression_included for pattern in report.patterns)
    assert all(pattern.support_count >= 2 for pattern in report.patterns)
    assert report.pattern_brief is not None
    assert report.pattern_brief.brand_id == "animal-x"
    assert report.pattern_brief.source_assets_allowed is False
    assert report.originality_gate is not None
    assert report.originality_gate.decision == GateDecision.REVIEW
    assert report.ready_for_human_review is True
    assert report.automatic_generation is False
    assert report.automatic_publication is False
    assert report.facets["brands"] == {"animal-x": 2, "rawr": 1}
    assert report_path.is_file()
    assert html_path.is_file()
    assert (report_path.parent / "pattern_library.json").is_file()
    assert (report_path.parent / "pattern_brief.json").is_file()
    assert (report_path.parent / "originality_gate.json").is_file()
    assert "Pattern and originality review" in html_path.read_text(encoding="utf-8")


def test_comparison_is_hash_resumable_and_deterministic(tmp_path: Path) -> None:
    paths = source_set(tmp_path / "references")
    first, _, _ = build_comparison_library(paths, tmp_path / "comparison")
    first_pairs = [item.model_dump() for item in first.pairwise]
    first_clusters = [item.model_dump() for item in first.clusters]

    second, _, _ = build_comparison_library(paths, tmp_path / "comparison")

    assert second.status == ComparisonStatus.REUSED
    assert [item.model_dump() for item in second.pairwise] == first_pairs
    assert [item.model_dump() for item in second.clusters] == first_clusters


def test_rights_or_transcript_change_invalidates_resume_and_removes_stale_brief(
    tmp_path: Path,
) -> None:
    paths = source_set(tmp_path / "references")[:2]
    output = tmp_path / "comparison"
    first, _, _ = build_comparison_library(paths, output)
    assert first.pattern_brief is not None
    assert (output / "pattern_brief.json").is_file()

    project_path = paths[0].parent.parent / "project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    project["access"] = {}
    project_path.write_text(json.dumps(project), encoding="utf-8")
    changed, _, _ = build_comparison_library(paths, output)

    assert changed.status == ComparisonStatus.BLOCKED
    assert changed.status != ComparisonStatus.REUSED
    assert changed.pattern_brief is None
    assert not (output / "pattern_brief.json").exists()
    assert not (output / "originality_gate.json").exists()


def test_bad_fingerprint_is_isolated_with_local_upload_fallback(tmp_path: Path) -> None:
    paths = source_set(tmp_path / "references")[:2]
    missing = tmp_path / "missing" / "reference_fingerprint.json"

    report, _, _ = build_comparison_library(
        [paths[0], missing, paths[1]],
        tmp_path / "comparison",
    )

    assert report.status == ComparisonStatus.PARTIAL
    assert report.reference_count == 2
    assert len(report.failures) == 1
    assert report.failures[0].input_label == "reference_fingerprint.json"
    assert "ingest-file" in report.failures[0].fallback_action
    assert "<local-path>" in report.failures[0].reason


def test_missing_rights_declaration_blocks_pattern_brief_readiness(tmp_path: Path) -> None:
    first = write_reference(
        tmp_path,
        "ref-one",
        title="One",
        rights=None,
        transcript="An original fixture transcript about seasonal animal migration.",
    )
    second = write_reference(
        tmp_path,
        "ref-two",
        title="Two",
        transcript="A separate fixture transcript about nocturnal animal behavior.",
    )

    report, _, _ = build_comparison_library([first, second], tmp_path / "comparison")

    assert report.status == ComparisonStatus.BLOCKED
    assert report.ready_for_human_review is False
    blocked = next(item for item in report.rights_gates if item.reference_id == "ref-one")
    assert blocked.decision == GateDecision.BLOCK
    assert blocked.comparison_allowed is False
    assert blocked.source_asset_use_allowed is False
    assert blocked.production_use_allowed is False


def test_originality_gate_blocks_transcript_and_title_reuse(tmp_path: Path) -> None:
    transcript = "The silver fox crossed the frozen river before the final storm arrived."
    path = write_reference(
        tmp_path,
        "ref-source",
        title="Silver Fox Chronicle",
        transcript=transcript,
    )
    report, _, _ = build_comparison_library(
        [
            path,
            write_reference(
                tmp_path,
                "ref-other",
                title="Other Reference",
                transcript="A completely different source fixture for deterministic comparison.",
            ),
        ],
        tmp_path / "comparison",
    )
    profile = next(item for item in report.profiles if item.reference_id == "ref-source")
    transcript_path = path.parent.parent / "transcript" / "transcript.txt"

    copied = evaluate_originality_text(
        transcript,
        [profile],
        {profile.reference_id: transcript_path},
    )
    titled = evaluate_originality_text(
        "Our next reel is Silver Fox Chronicle with a new ending.",
        [profile],
        {profile.reference_id: transcript_path},
    )

    assert copied.decision == GateDecision.BLOCK
    assert copied.checks[0].longest_shared_phrase_words >= 8
    assert copied.checks[0].source_excerpt_persisted is False
    assert titled.decision == GateDecision.BLOCK
    assert titled.checks[0].source_title_reused is True


def test_missing_transcript_never_becomes_a_false_originality_pass(tmp_path: Path) -> None:
    profile = ReferenceProfile(
        reference_id="ref-no-text",
        title="Unavailable Transcript",
        platform="facebook",
        brand_id="animal-x",
        format_name="vertical_short",
        rights_declaration="public-internal-research",
        fingerprint_sha256="a" * 64,
        hook_type="curiosity",
        story_stages=["setup", "payoff"],
        pacing={},
        visual_terms=[],
        audio_terms=[],
        mechanics_terms=[],
        source_specific_elements_to_exclude=[],
    )

    gate = evaluate_originality_text("A new candidate brief", [profile], {"ref-no-text": None})

    assert gate.decision == GateDecision.REVIEW
    assert gate.limitations
    assert gate.automatic_approval is False
    assert gate.human_review_required is True


def test_pattern_brief_excludes_protected_source_categories(tmp_path: Path) -> None:
    paths = source_set(tmp_path / "references")
    report, _, _ = build_comparison_library(paths, tmp_path / "comparison")
    assert report.pattern_brief is not None
    rendered = report.pattern_brief.model_dump_json().lower()
    for required in ("identities", "watermarks", "voice", "music", "human"):
        assert required in rendered
    for title in ("reference alpha", "reference beta", "reference gamma"):
        assert title not in rendered


def test_metadata_loader_rejects_non_mapping_and_normalizes_values(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(
        json.dumps({"ref-one": {"brand_id": "animal-x", "format_name": "reel"}}),
        encoding="utf-8",
    )
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")

    assert load_comparison_metadata(valid) == {
        "ref-one": {"brand_id": "animal-x", "format_name": "reel"}
    }
    try:
        load_comparison_metadata(invalid)
    except ValueError as exc:
        assert "object keyed by reference ID" in str(exc)
    else:
        raise AssertionError("non-mapping metadata must fail closed")
