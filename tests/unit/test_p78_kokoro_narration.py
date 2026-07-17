from pathlib import Path

from src.p78_kokoro_narration import MODEL_ID, PROVIDER, proportional_alignment


def test_proportional_alignment_covers_the_full_duration() -> None:
    rows = proportional_alignment("A gecko grips glass.", 3.25)

    assert rows[0]["startSec"] == 0.0
    assert rows[-1]["endSec"] == 3.25
    assert all(row["timingBasis"] == "proportional_estimate" for row in rows)
    assert all(current["endSec"] <= following["startSec"] for current, following in zip(rows, rows[1:]))


def test_proportional_alignment_handles_empty_text() -> None:
    assert proportional_alignment("", 2.0) == []


def test_local_provider_contract_is_explicit() -> None:
    assert PROVIDER == "kokoro-onnx"
    assert MODEL_ID == "hexgrad/Kokoro-82M-v1.0-onnx"


def test_generation_script_defaults_to_local_runtime() -> None:
    script = Path("scripts/p78_generate_kokoro_narration.py").read_text(encoding="utf-8")

    assert ".runtime/kokoro-models/kokoro-v1.0.onnx" in script
    assert ".runtime/kokoro-models/voices-v1.0.bin" in script
    assert "KOKORO_RUNTIME_DIR" in script
    assert "vercel" not in script.lower()


def test_narrated_review_remains_non_publishable() -> None:
    script = Path("scripts/p78_build_narrated_visual_review.py").read_text(encoding="utf-8")

    assert '"publish_allowed": False' in script
    assert '"approval_allowed": True' in script
    assert '["S01", "S06"]' in script
    assert "planned_duration - 0.25" in script


def test_portfolio_bridge_prefers_narrated_review_over_silent_review() -> None:
    bridge = Path("src/p76_portfolio_bridge.py").read_text(encoding="utf-8")
    narrated = bridge.index('"narrated-visual-v1"')
    silent = bridge.index('"visual-v1"')

    assert narrated < silent
