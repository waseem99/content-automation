from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "web/static-creator-ui/assets/portfolio-api.js"
MODULE = ROOT / "web/static-creator-ui/assets/visual-candidates.js"
STYLE = ROOT / "web/static-creator-ui/assets/visual-candidates.css"


def test_visual_candidate_module_is_loaded_by_studio_registry() -> None:
    api = API.read_text(encoding="utf-8")
    assert '["visual-candidates", "visual-candidates.css", "visual-candidates.js"]' in api
    assert "visualsForContent" in api
    assert "initializeVisuals" in api
    assert "decideVisualCandidate" in api
    assert "decideVisualShot" in api
    assert "reviseVisualShot" in api
    assert "submitVisualProject" in api
    assert "decideVisualProject" in api


def test_visual_candidate_panel_is_retained_evidence_and_review_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "Local Visual Candidate Review" in source
    assert "Compare retained shot candidates" in source
    assert "exact prompt, seed, model, references, and ten-check evidence" in source
    assert "Prior candidates remain retained" in source
    assert "child prompt version" in source
    assert "Select" in source
    assert "Reject" in source
    assert "Revise this prompt" in source
    assert "registerVisualCandidateResult" not in source
    assert "/result" not in source
    assert "upload" not in source.lower()
    assert "publish" not in source.lower()
    assert "worker" not in source.lower()
    assert "motion" not in source.lower()
    assert "X-Operator-Key" not in source
    assert "openai" not in source.lower()
    assert "replicate" not in source.lower()


def test_visual_candidate_styles_are_present() -> None:
    style = STYLE.read_text(encoding="utf-8")
    assert ".visual-candidates-section" in style
    assert ".visual-candidate-grid" in style
    assert ".visual-candidate-check" in style
    assert ".visual-candidates-badge" in style
