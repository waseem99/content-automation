from pathlib import Path

import pytest

from src.application.reference_intelligence_service import (
    sanitize_diagnostic,
    sanitize_review_metadata,
    sanitize_source_url,
    validate_job_transition,
    validate_local_locator,
)


ROOT = Path(__file__).resolve().parents[2]


def test_reference_sanitizers_keep_public_identity_without_secrets() -> None:
    value = sanitize_source_url(
        "https://user:pass@YouTube.com/watch?v=abc&token=secret&signature=nope#part"
    )
    assert value == "https://youtube.com/watch?v=abc"
    assert sanitize_diagnostic("token=secret at /home/operator/private/file.mp4") == (
        "token=<redacted> at <local-path>"
    )
    assert sanitize_review_metadata(
        {"token": "secret", "note": "read /home/operator/private/file.mp4"}
    ) == {"note": "read <local-path>"}


def test_reference_job_and_artifact_guards_are_terminal_safe() -> None:
    validate_job_transition("queued", "running")
    validate_job_transition("running", "succeeded")
    with pytest.raises(ValueError):
        validate_job_transition("succeeded", "running")
    assert validate_local_locator("reference://ref-1/frames/contact_sheet.jpg")
    with pytest.raises(ValueError):
        validate_local_locator("reference://ref-1/source/original.mp4")


def test_reference_schema_api_and_static_ui_preserve_runtime_boundary() -> None:
    migration = (ROOT / "migrations" / "0027_reference_intelligence_portfolio.sql").read_text()
    api = (ROOT / "src" / "operator_api" / "app.py").read_text()
    html = (ROOT / "web" / "static-creator-ui" / "index.html").read_text()
    js = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text()
    for table in (
        "reference_sources",
        "reference_ingestion_jobs",
        "reference_artifacts",
        "reference_brand_assignments",
        "reference_approval_gates",
        "research_idea_links",
    ):
        assert f"CREATE TABLE football_brief.{table}" in migration
    assert "CHECK (source_media_synced = false)" in migration
    assert "CHECK (automatic_decision = false)" in migration
    assert 'worker_mode text NOT NULL DEFAULT \'local\'' in migration
    for route in (
        '"/portfolio/references"',
        '"/portfolio/references/{source_id}"',
        '"/portfolio/reference-jobs/{job_id}/progress"',
    ):
        assert route in api
    assert 'id="reference-intelligence"' in html
    assert "source files stay in the local workspace" in html
    assert "decideReferenceGate" in js
    assert "sessionStorage" in js
    assert "/publish" not in js
