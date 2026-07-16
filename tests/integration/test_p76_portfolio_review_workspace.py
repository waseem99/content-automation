from pathlib import Path

from src.application.portfolio_service import approval_prerequisites


ROOT = Path(__file__).resolve().parents[2]


def test_approval_prerequisites_protect_script_and_preview_gates():
    assert approval_prerequisites(stage="idea", item={}, artifacts=[]) == []
    assert approval_prerequisites(stage="script", item={}, artifacts=[]) == ["script", "scene_plan"]
    assert approval_prerequisites(
        stage="script", item={"script": {"hook": "x"}, "scene_plan": {"scenes": []}}, artifacts=[]
    ) == []
    assert approval_prerequisites(stage="preview", item={}, artifacts=[]) == ["voiceover", "preview"]
    assert approval_prerequisites(
        stage="preview",
        item={},
        artifacts=[
            {"kind": "voiceover", "review_status": "pending"},
            {"kind": "preview", "review_status": "pending"},
        ],
    ) == []


def test_superseded_media_does_not_satisfy_preview_gate():
    missing = approval_prerequisites(
        stage="preview",
        item={},
        artifacts=[
            {"kind": "voiceover", "review_status": "superseded"},
            {"kind": "preview", "review_status": "pending"},
        ],
    )
    assert missing == ["voiceover"]


def test_review_workspace_migration_is_local_media_safe():
    sql = (ROOT / "migrations" / "0028_portfolio_review_workspace.sql").read_text()
    assert "CREATE TABLE football_brief.portfolio_content_artifacts" in sql
    assert "local_locator ~ '^content://" in sql
    assert "portfolio_content_artifacts_review_idx" in sql
    assert "source_url" not in sql


def test_operator_api_exposes_workspace_without_upload_or_publish_route():
    source = (ROOT / "src" / "operator_api" / "app.py").read_text()
    for route in (
        '/portfolio/content/{content_id}',
        '/portfolio/content/{content_id}/workspace',
        '/portfolio/content/{content_id}/artifacts',
        '/portfolio/content/{content_id}/artifacts/{artifact_id}/media',
    ):
        assert route in source
    assert 'PORTFOLIO_MEDIA_ROOT' in source
    assert '/portfolio/content/{content_id}/upload' not in source
    assert '/portfolio/publish' not in source


def test_creator_ui_has_real_review_workspace_and_no_prompt_approval():
    html = (ROOT / "web" / "static-creator-ui" / "index.html").read_text()
    app = (ROOT / "web" / "static-creator-ui" / "assets" / "app.js").read_text()
    api = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text()
    assert 'id="content-review"' in html
    assert 'id="review-script"' in app
    assert 'data-review-decision="changes_requested"' in app
    assert "missing_for_approval" in app
    assert "PortfolioApi.content" in app
    assert "updateWorkspace" in api
    assert "mediaHeaders" in api
    assert "Approve the ${gate}" not in app


def test_local_compose_mounts_review_media_read_only():
    compose = (ROOT / "deploy" / "portfolio-staging" / "compose.yaml").read_text()
    assert "PORTFOLIO_MEDIA_ROOT: /workspace/portfolio-media" in compose
    assert "/workspace/portfolio-media:ro" in compose
