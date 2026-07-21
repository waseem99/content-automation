from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_concept_studio_is_loaded_and_remains_review_only() -> None:
    client = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text(encoding="utf-8")
    studio = (ROOT / "web" / "static-creator-ui" / "assets" / "concept-slate.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "static-creator-ui" / "assets" / "concept-slate.css").read_text(encoding="utf-8")

    assert '["concept-slate", "concept-slate.css", "concept-slate.js"]' in client
    assert 'adapter_mode: "deterministic"' in studio
    assert "Generate deterministic candidates" in studio
    assert "No plan is changed until administrator application" in studio
    assert 'rolesInclude("reviewer")' in studio
    assert 'rolesInclude("admin")' in studio
    assert "/concepts/slates/${slateId}/apply" in studio
    assert "local_model" not in studio
    assert "paid_provider" not in studio
    assert "openai" not in studio.lower()
    assert "anthropic" not in studio.lower()
    assert "gemini" not in studio.lower()
    assert ".concept-slate-section" in styles
    assert ".concept-card" in styles


def test_concept_studio_does_not_expose_automatic_plan_application() -> None:
    studio = (ROOT / "web" / "static-creator-ui" / "assets" / "concept-slate.js").read_text(encoding="utf-8")

    generate_start = studio.index("async function generate()")
    generate_end = studio.index("async function initializeData()")
    generate_body = studio[generate_start:generate_end]
    assert "/concepts/batches" in generate_body
    assert "/apply" not in generate_body
    assert "plan_id" not in generate_body

    apply_start = studio.index("async function applySlate")
    apply_end = studio.index("async function loadBatch")
    apply_body = studio[apply_start:apply_end]
    assert "window.prompt" in apply_body
    assert "Draft monthly plan UUID" in apply_body
    assert "/apply" in apply_body
