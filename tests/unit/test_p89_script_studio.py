from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_script_review_studio_is_loaded_and_keeps_downstream_work_hidden() -> None:
    client = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text(encoding="utf-8")
    studio = (ROOT / "web" / "static-creator-ui" / "assets" / "script-review.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "static-creator-ui" / "assets" / "script-review.css").read_text(encoding="utf-8")

    assert '["script-review", "script-review.css", "script-review.js"]' in client
    assert 'adapter_mode: "deterministic"' in studio
    assert "Submit exact version" in studio
    assert "Add review action" in studio
    assert "Create child revision" in studio
    assert "/scripts/${state.data.document.id}/decisions" in studio
    assert "/scripts/${state.data.document.id}/revise" in studio
    assert "local_model" not in studio
    assert "generation/jobs" not in studio
    assert "narration" not in studio.lower() or "before narration" in studio.lower()
    assert ".script-review-section" in styles
    assert ".script-review-evidence" in styles


def test_generate_action_cannot_submit_or_start_downstream_jobs() -> None:
    studio = (ROOT / "web" / "static-creator-ui" / "assets" / "script-review.js").read_text(encoding="utf-8")
    start = studio.index("async function generate()")
    end = studio.index("async function submit()")
    body = studio[start:end]

    assert "/scripts/content/" in body
    assert "/submit" not in body
    assert "/decisions" not in body
    assert "generation/jobs" not in body
    assert "preview" not in body.lower()
