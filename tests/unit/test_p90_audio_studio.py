from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "web/static-creator-ui/assets/portfolio-api.js"
MODULE = ROOT / "web/static-creator-ui/assets/audio-review.js"
STYLE = ROOT / "web/static-creator-ui/assets/audio-review.css"


def test_audio_review_module_is_loaded_by_studio_registry() -> None:
    api = API.read_text(encoding="utf-8")
    assert '["audio-review", "audio-review.css", "audio-review.js"]' in api
    assert "audioForContent" in api
    assert "initializeAudio" in api
    assert "regenerateAudioParagraph" in api


def test_audio_review_is_local_evidence_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "Local Narration Review" in source
    assert "Kokoro remains local and zero-fee" in source
    assert "forced alignment" in source
    assert "QC" in source
    assert "Regenerate this paragraph" in source
    assert "paid-provider" not in source
    assert "upload" not in source.lower()
    assert "mediaUrl" not in source
    assert "X-Operator-Key" not in source


def test_audio_review_styles_are_present() -> None:
    style = STYLE.read_text(encoding="utf-8")
    assert ".audio-review-section" in style
    assert ".audio-review-grid" in style
    assert ".audio-review-badge" in style
