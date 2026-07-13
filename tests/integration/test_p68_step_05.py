from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "src" / "p68_clip_stitcher.py"
DOC = ROOT / "docs" / "operations" / "p68-step-05.md"


def test_p68_step_05_has_provider_neutral_real_media_assembly() -> None:
    content = ENGINE.read_text(encoding="utf-8")
    for term in [
        "validate_clip_manifest",
        "provider_lineage_required",
        "normalize_clip",
        "scale=1080:1920",
        "fps=30",
        "libx264",
        "transition_schedule",
        "j_cut",
        "l_cut",
        "MAX_CROSSFADE_SECONDS = 0.3",
        "finish_master",
        "amix",
        "loudnorm=I=-14",
        "subtitles=",
        "assemble_clip_plan",
        "render_manifest.json",
        '"quality_approved": False',
        '"publish_allowed": False',
    ]:
        assert term in content


def test_p68_step_05_documentation_preserves_review_and_publish_gates() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #714. Closes #719 after the PR merges.",
        "generated or approved clips",
        "exact planned shot order",
        "1080×1920",
        "30 fps",
        "H.264/AAC",
        "direct, action, and match cuts",
        "J-cut and L-cut",
        "300 ms",
        "continuous narration, music, and ambience",
        "Kokoro",
        "captions",
        "-14 LUFS",
        "does not call a clip-generation provider",
        "No automatic publishing",
        "quality_approved: false",
        "publish_allowed: false",
    ]:
        assert term in content
