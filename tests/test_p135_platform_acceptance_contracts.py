from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_playwright_dependencies_are_pinned() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["@playwright/test"] == "1.62.1"
    assert package["devDependencies"]["@axe-core/playwright"] == "4.12.1"
    assert package["engines"]["node"] == ">=20"


def test_no_cost_runner_fails_closed_on_spend_and_publishing_flags() -> None:
    script = (ROOT / "scripts/windows/run_platform_acceptance.ps1").read_text(encoding="utf-8")
    assert 'Assert-Disabled $values "PROVIDER_PAID_EXECUTION_ENABLED"' in script
    assert 'Assert-Disabled $values "HYBRID_PAID_EXECUTION_ENABLED"' in script
    assert 'Assert-Disabled $values "HYBRID_PUBLIC_PUBLISHING_ENABLED"' in script
    assert "pre-run-postgres.dump" in script


def test_live_provider_runner_requires_explicit_bounded_confirmation() -> None:
    script = (ROOT / "scripts/windows/run_live_provider_acceptance.ps1").read_text(encoding="utf-8")
    assert "MaximumSpendUsd -le 0" in script
    assert "MaximumSpendUsd -gt 1" in script
    assert '"SPEND-$($Provider.ToUpperInvariant())-' in script
    assert "PLATFORM_LIVE_RESERVATION_PAYLOAD_FILE" in script


def test_release_sync_records_real_git_and_non_secret_configuration_digest() -> None:
    script = (ROOT / "scripts/windows/sync_p131_environment.ps1").read_text(encoding="utf-8")
    assert "git -C $Root rev-parse HEAD" in script
    assert "OPS_CONFIGURATION_DIGEST" in script
    assert "OPERATOR_API_KEYS_JSON" in script
    assert "Security.Cryptography.SHA256" in script


def test_browser_suite_contains_required_acceptance_surfaces() -> None:
    tests = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests/e2e").glob("*.spec.js"))
    )
    for marker in (
        "/runtime/ready",
        "/app/campaigns",
        "/app/content",
        "/app/reviews",
        "/app/operations",
        "@live-provider",
        "@smoke",
    ):
        assert marker in tests


def test_static_creator_ui_does_not_consume_the_api_rate_window() -> None:
    settings = (ROOT / "src/operations/settings.py").read_text(encoding="utf-8")
    environment = (ROOT / "config/local.env.example").read_text(encoding="utf-8")
    sync = (ROOT / "scripts/windows/sync_p131_environment.ps1").read_text(encoding="utf-8")
    assert '"/app",' in settings
    assert '"/favicon.ico",' in settings
    assert "rate_limit_exempt_prefixes" in settings
    assert '"/app/"' in settings
    assert '"/assets/"' in settings
    assert 'OPS_RATE_LIMIT_EXEMPT_PATHS=["/app","/favicon.ico","/health","/runtime/ready"]' in environment
    assert 'OPS_RATE_LIMIT_EXEMPT_PREFIXES=["/app/","/assets/"]' in environment
    assert '$values["OPS_RATE_LIMIT_EXEMPT_PATHS"]' in sync
    assert '$values["OPS_RATE_LIMIT_EXEMPT_PREFIXES"]' in sync

    middleware = (ROOT / "src/operator_api/operations_middleware.py").read_text(encoding="utf-8")
    assert "if not self._rate_limit_exempt(path):" in middleware
    assert "self.settings.rate_limit_exempt_prefixes" in middleware
    assert "path.startswith(prefix)" in middleware


def test_campaign_extension_direct_routes_reconcile_after_core_router_boot() -> None:
    index = (ROOT / "web/static-creator-ui/index.html").read_text(encoding="utf-8")
    bridge = (ROOT / "web/static-creator-ui/assets/studio-v2-route-bridge.js").read_text(encoding="utf-8")
    assert '<link rel="icon" href="data:,">' in index
    assert "studio-v2-route-bridge.js" in index
    assert 'title === "Page not found"' in bridge
    assert 'new PopStateEvent("popstate"' in bridge
    assert "link.click()" not in bridge
    assert "history.pushState" not in bridge


def test_browser_monitor_classifies_expected_http_failures_without_hiding_javascript_errors() -> None:
    support = (ROOT / "tests/e2e/support.js").read_text(encoding="utf-8")
    assert "clientErrors" in support
    assert "allowedClientErrors" in support
    assert "Unexpected client HTTP errors" in support
    assert "navigateApp" in support
    assert "Failed to load resource" in support
