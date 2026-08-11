from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linearize(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearize(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def test_campaign_route_recovery_preserves_deep_link_path() -> None:
    bridge = (
        ROOT / "web/static-creator-ui/assets/studio-v2-route-bridge.js"
    ).read_text(encoding="utf-8")
    campaign_module = (
        ROOT / "web/static-creator-ui/assets/studio-v2-campaigns.js"
    ).read_text(encoding="utf-8")

    assert 'new PopStateEvent("popstate"' in bridge
    assert "link.click()" not in bridge
    assert "history.pushState" not in bridge
    assert "recoveryAttempts >= 40" in bridge
    assert 'window.addEventListener("popstate"' in campaign_module
    assert "void renderRoute(true)" in campaign_module


def test_creator_studio_eyebrow_meets_wcag_aa_normal_text_contrast() -> None:
    accessibility = (
        ROOT / "web/static-creator-ui/assets/studio-v2-accessibility.css"
    ).read_text(encoding="utf-8")
    index = (ROOT / "web/static-creator-ui/index.html").read_text(encoding="utf-8")

    assert "--eyebrow-accessible:#175cd3" in accessibility
    assert ".eyebrow" in accessibility
    assert "color:var(--eyebrow-accessible)" in accessibility
    assert _contrast_ratio("#175cd3", "#fefeff") >= 4.5
    assert index.index("studio-v2.css") < index.index("studio-v2-accessibility.css")


def test_changed_browser_assets_are_cache_busted() -> None:
    index = (ROOT / "web/static-creator-ui/index.html").read_text(encoding="utf-8")

    assert "studio-v2-accessibility.css?v=p135-20260804-1" in index
    assert "studio-v2-route-bridge.js?v=p135-20260804-1" in index


def test_mutating_content_fixture_is_unique_across_consecutive_acceptance_runs() -> None:
    lifecycle = (ROOT / "tests/e2e/07-content-lifecycle.spec.js").read_text(encoding="utf-8")

    assert "const id = runId();" in lifecycle
    assert "for acceptance run ${id}" in lifecycle
    assert "Automated QA run ${id}" in lifecycle


def test_runtime_http_exception_payloads_are_json_safe() -> None:
    entrypoint = (ROOT / "src/operator_api/entrypoint.py").read_text(encoding="utf-8")

    assert "jsonable_encoder" in entrypoint
    assert 'jsonable_encoder({"detail": exc.detail})' in entrypoint
    assert "application.add_exception_handler(" in entrypoint
    assert "StarletteHTTPException" in entrypoint


def test_always_on_parent_imports_environment_before_continuation_worker() -> None:
    supervisor = (
        ROOT / "scripts/windows/supervise_always_on_local_production.ps1"
    ).read_text(encoding="utf-8")

    sync_index = supervisor.index("& $SyncP131 -Path $EnvPath")
    import_index = supervisor.index("Import-LocalEnvironment $EnvPath")
    continuation_index = supervisor.index("function Start-Continuation")

    assert sync_index < import_index < continuation_index
    assert 'SetEnvironmentVariable([string]$parts[0], [string]$parts[1], "Process")' in supervisor
