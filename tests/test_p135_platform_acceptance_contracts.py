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
