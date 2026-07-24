from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-extensions.js"


def test_publishing_view_does_not_reenter_after_successful_render() -> None:
    source = EXTENSIONS.read_text(encoding="utf-8")

    assert 'id="publisher-workspace"' in source
    assert 'view.dataset.publisherReady === "true"' in source
    assert 'view.dataset.publisherReady = "false"' in source
    assert 'view.dataset.publisherReady = "true"' in source
    assert 'renderPublishing({ force: true })' in source


def test_publishing_guard_requires_the_rendered_workspace_marker() -> None:
    source = EXTENSIONS.read_text(encoding="utf-8")

    assert '$("#publisher-workspace", view)' in source
    assert 'view.dataset.extensionRoute === "publishing"' in source
