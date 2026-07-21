from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "web/static-creator-ui/assets/portfolio-api.js"
MODULE = ROOT / "web/static-creator-ui/assets/review-workspace.js"
STYLE = ROOT / "web/static-creator-ui/assets/review-workspace.css"


def test_review_workspace_module_is_loaded_and_uses_scoped_clients() -> None:
    api = API.read_text(encoding="utf-8")
    assert '["review-workspace", "review-workspace.css", "review-workspace.js"]' in api
    for method in (
        "reviewInbox",
        "reviewWorkspace",
        "compareReview",
        "createReviewComment",
        "resolveReviewComment",
        "mutateRevisionTask",
        "decideScript",
        "decideAudio",
        "decideVisualCandidate",
        "decideVisualShot",
        "decideVisualProject",
    ):
        assert method in api


def test_review_workspace_contains_required_evidence_and_forms() -> None:
    source = MODULE.read_text(encoding="utf-8")
    required = (
        "Creator Studio Review Workspace",
        "Review inbox, exact versions, comments, and revisions",
        "All assigned brands",
        "Blockers only",
        "Overdue only",
        "Narration & mix",
        "Waveform timeline placeholder",
        "Shots & retained candidates",
        "Render placeholders",
        "Compare versions",
        "Comment on exact evidence",
        "Structured revision task",
        "Decision history",
        "Accept",
        "Return",
        "Request shot changes",
    )
    for value in required:
        assert value in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert 'aria-label="Review inbox"' in source
    assert 'aria-selected="true"' in source
    assert "target_type" in source
    assert "timeline_start_ms" in source
    assert "assignee_operator_id" in source
    assert "expected_lock_version" in source


def test_review_workspace_has_no_raw_or_execution_controls() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    assert "json.parse" not in source
    assert 'type="file"' not in source
    assert "upload" not in source
    assert "storage_uri" not in source
    assert "x-operator-key" not in source
    assert "provider key" not in source
    assert "preferred_worker" not in source
    assert "publish" not in source
    assert "enqueueassembly" not in source


def test_review_workspace_styles_are_responsive_and_accessible() -> None:
    style = STYLE.read_text(encoding="utf-8")
    assert ".review-workspace-layout" in style
    assert ".review-inbox-panel" in style
    assert ".review-evidence-grid" in style
    assert ".review-waveform" in style
    assert ".review-compare-columns" in style
    assert ".review-comment-columns" in style
    assert "@media(max-width:1180px)" in style
    assert "@media(max-width:820px)" in style
    assert "@media(max-width:560px)" in style
    assert ':focus-visible' in style
