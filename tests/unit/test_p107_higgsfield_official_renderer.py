from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.application.renderers.higgsfield_cli import (
    HiggsfieldCliError,
    HiggsfieldCliRendererAdapter,
)
from src.operations.higgsfield_worker import HiggsfieldManagedWorker


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "src" / "operations" / "higgsfield_worker.py"
ONBOARDING = ROOT / "src" / "operations" / "local_onboarding_v2.py"
SUPERVISOR = ROOT / "scripts" / "windows" / "supervise_local_production.ps1"
SETUP = ROOT / "scripts" / "windows" / "setup_higgsfield_official.ps1"


def adapter_without_init() -> HiggsfieldCliRendererAdapter:
    return object.__new__(HiggsfieldCliRendererAdapter)


def test_official_cli_arguments_are_reviewed_and_secret_free(tmp_path: Path) -> None:
    adapter = adapter_without_init()
    image = tmp_path / "start.png"
    image.write_bytes(b"image")
    arguments = adapter._generation_arguments(
        request_payload={
            "duration_seconds": "5",
            "width": 720,
            "height": 1280,
        },
        metadata={
            "higgsfield_cli_arguments": [
                "--prompt",
                "An original approved wildlife shot",
                "--start-image",
                "{input_asset_0}",
                "--duration",
                "5",
            ]
        },
        input_paths=[image],
    )
    assert str(image) in arguments
    assert "--json" not in arguments
    assert "--no-color" not in arguments

    with pytest.raises(HiggsfieldCliError) as forbidden:
        adapter._validate_arguments(["--api-key", "not-allowed"])
    assert forbidden.value.code == "higgsfield_secret_argument_forbidden"


def test_provider_state_normalizes_success_output_and_cost() -> None:
    adapter = adapter_without_init()
    state = adapter._state(
        "generation-1",
        {
            "status": "completed",
            "result": {"video_url": "https://cdn.example.test/output.mp4"},
            "billing": {"actual_cost_usd": "1.25"},
        },
    )
    assert state.status == "succeeded"
    assert state.output_url == "https://cdn.example.test/output.mp4"
    assert state.actual_cost_usd == Decimal("1.25")
    assert state.terminal is True


def test_cost_fallback_never_understates_the_approved_ceiling() -> None:
    cost = HiggsfieldManagedWorker._cost_or_conservative_ceiling(
        {"reserved_cost_usd": "3.50", "estimated_cost_usd": "2.00"},
        None,
    )
    assert cost == Decimal("3.50")
    assert HiggsfieldManagedWorker._cost_or_conservative_ceiling(
        {"reserved_cost_usd": "3.50", "estimated_cost_usd": "2.00"},
        Decimal("1.75"),
    ) == Decimal("1.75")


def test_worker_registers_only_pending_review_shared_artifacts() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "GenerationJobType.PREMIUM_CLIP" in source
    assert 'providers=("higgsfield",)' in source
    assert "shared_artifact_version_id" in source
    assert '"review_status": "pending"' in source
    assert '"automatic_approval": False' in source
    assert '"external_fee_incurred": True' in source
    assert "jobs.complete" in source
    assert "jobs.fail" in source


def test_worker_identity_has_no_api_key_and_only_internal_producer_capability() -> None:
    source = ONBOARDING.read_text(encoding="utf-8")
    assert '"higgsfield-worker"' in source
    assert "api_key_created" in source
    assert "False" in source
    assert "VALUES (%s,'producer',%s)" in source


def test_supervisor_runs_higgsfield_only_when_explicitly_enabled() -> None:
    source = SUPERVISOR.read_text(encoding="utf-8")
    assert "src.operations.higgsfield_worker" in source
    assert "HIGGSFIELD_ENABLED" in source
    assert "automatic_spend_approval = $false" in source
    assert "external_fee_possible" in source


def test_setup_uses_only_official_cli_and_cannot_spend_automatically() -> None:
    source = SETUP.read_text(encoding="utf-8")
    assert "npm install --global @higgsfield/cli" in source
    assert "higgsfield auth login" in source
    assert "higgsfield model get" in source
    assert 'provider_key = "higgsfield"' in source
    assert 'adapter_kind = "managed_sdk"' in source
    assert 'pricing = @{ per_second = [string]$PricePerSecondUsd }' in source
    assert "automatic_spend_approval = $false" in source
    assert "No generation or credit spend was triggered" in source
    assert "generate create" not in source


def test_error_messages_are_redacted_when_credentials_are_mentioned() -> None:
    adapter = adapter_without_init()
    assert "redacted" in adapter._redacted_error("authorization token abc123 failed").lower()
    assert adapter._redacted_error("temporary rate limit") == "temporary rate limit"
