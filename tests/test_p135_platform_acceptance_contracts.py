from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def test_playwright_dependencies_are_pinned() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["@playwright/test"] == "1.62.1"
    assert package["devDependencies"]["@axe-core/playwright"] == "4.12.1"
    assert package["engines"]["node"] == ">=20"


def test_no_cost_runner_fails_closed_on_spend_publishing_and_unsanitized_evidence() -> None:
    script = (ROOT / "scripts/windows/run_platform_acceptance.ps1").read_text(encoding="utf-8")
    assert 'Assert-Disabled $values "PROVIDER_PAID_EXECUTION_ENABLED"' in script
    assert 'Assert-Disabled $values "HYBRID_PAID_EXECUTION_ENABLED"' in script
    assert 'Assert-Disabled $values "HYBRID_PUBLIC_PUBLISHING_ENABLED"' in script
    assert "pre-run-postgres.dump" in script
    assert "scripts\\sanitize_platform_evidence.py" in script
    assert "& $Python $EvidenceSanitizer --root $RunDir" in script
    assert "Platform evidence sanitization failed. Do not share or upload this run directory." in script
    assert script.index("& $Python $EvidenceSanitizer --root $RunDir") < script.index(
        "Remove-Item Env:PLATFORM_ADMIN_KEY"
    )


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


def test_campaign_extension_direct_routes_reconcile_without_collapsing_deep_links() -> None:
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


def test_campaign_pause_and_resume_wait_for_the_exact_mutation_response() -> None:
    source = (ROOT / "tests/e2e/02-campaign-lifecycle.spec.js").read_text(encoding="utf-8")
    assert "clickCampaignStatusAction" in source
    assert "page.waitForResponse" in source
    assert "waitForCampaignStatus" in source
    assert "await expect(button).toBeVisible()" in source
    assert "pause.isVisible().catch" not in source


def test_content_creation_reports_the_exact_sanitized_api_result_before_url_assertion() -> None:
    source = (ROOT / "tests/e2e/07-content-lifecycle.spec.js").read_text(encoding="utf-8")
    assert "url.pathname === '/p110/content'" in source
    assert "content-create-response" in source
    assert "sanitizedPayload" in source
    assert source.index("createResponse.status()") < source.index("toHaveURL")
    assert "timeout: 90_000" in source


def test_fal_wan_uses_one_fixed_request_charge_and_safe_versioned_upgrade() -> None:
    setup = (ROOT / "scripts/windows/setup_provider_first_rendering.ps1").read_text(encoding="utf-8")
    estimate = (ROOT / "src/application/renderers/validated_service.py").read_text(encoding="utf-8")
    migration = (ROOT / "src/operations/fal_fixed_request_pricing.py").read_text(encoding="utf-8")
    deploy = (ROOT / "scripts/windows/deploy_remote_content_automation.ps1").read_text(encoding="utf-8")
    assert "FalPricePerRequestUsd" in setup
    assert "FalPricePerSecondUsd" not in setup
    assert "per_request_usd" in setup
    assert "fixed_request_billing" in setup
    assert '_decimal(pricing.get("per_request_usd"))' in estimate
    assert "ValidatedRendererCatalogueService" in migration
    assert 'if key not in {"per_second_usd", "base_usd", "per_request_usd"}' in migration
    assert 'upgraded["per_request_usd"] = legacy_value' in migration
    assert "src.operations.fal_fixed_request_pricing" in deploy


def test_evidence_sanitizer_redacts_plain_archived_and_embedded_report_values(tmp_path: Path) -> None:
    secret = "acceptance-secret-value-123456789"
    trace = tmp_path / "trace.zip"
    with zipfile.ZipFile(trace, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trace.trace", json.dumps({"step": f'Fill "{secret}"'}))
        archive.writestr("trace.network", json.dumps({"headers": {"X-Operator-Key": secret}}))

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("test.json", json.dumps({"title": f'Fill "{secret}" locator'}))
        archive.writestr("network.json", json.dumps({"operator": secret}))
    report = tmp_path / "index.html"
    report.write_bytes(
        b"<html><script>data:application/zip;base64,"
        + base64.b64encode(inner.getvalue())
        + b"</script></html>"
    )
    (tmp_path / "results.json").write_text(json.dumps({"operator_key": secret}), encoding="utf-8")

    environment = os.environ.copy()
    environment["PLATFORM_ADMIN_KEY"] = secret
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sanitize_platform_evidence.py"), "--root", str(tmp_path)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert secret.encode() not in trace.read_bytes()
    assert secret.encode() not in report.read_bytes()
    assert secret not in (tmp_path / "results.json").read_text(encoding="utf-8")

    with zipfile.ZipFile(trace, "r") as archive:
        assert secret not in archive.read("trace.trace").decode("utf-8")
        assert secret not in archive.read("trace.network").decode("utf-8")

    encoded = report.read_bytes().split(b"data:application/zip;base64,", 1)[1].split(b"<", 1)[0]
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded)), "r") as archive:
        assert secret not in archive.read("test.json").decode("utf-8")
        assert secret not in archive.read("network.json").decode("utf-8")

    summary = json.loads((tmp_path / "evidence-sanitization.json").read_text(encoding="utf-8"))
    assert summary["status"] == "passed"
    assert summary["secret_values_recorded"] is False
    assert summary["redactions"] >= 4
