from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.application.renderers.fal_api import FalQueueRendererAdapter
from src.application.renderers.provider_http import ManagedHttpAdapter, ManagedProviderError
from src.application.renderers.vidu_api import ViduRendererAdapter
from src.operations.provider_managed_worker import ProviderManagedWorker


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "src" / "operations" / "provider_managed_worker.py"
ONBOARDING = ROOT / "src" / "operations" / "provider_worker_onboarding.py"
SUPERVISOR = ROOT / "scripts" / "windows" / "supervise_provider_workers.ps1"
SETUP = ROOT / "scripts" / "windows" / "setup_provider_first_rendering.ps1"
DOC = ROOT / "docs" / "operations" / "PROVIDER_FIRST_VIDEO_PRODUCTION.md"


def test_data_uri_accepts_only_reviewed_image_formats(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"reviewed-image")
    value = ManagedHttpAdapter.data_uri(image)
    assert value.startswith("data:image/png;base64,")

    text = tmp_path / "secret.txt"
    text.write_text("not an image", encoding="utf-8")
    with pytest.raises(ManagedProviderError) as error:
        ManagedHttpAdapter.data_uri(text)
    assert error.value.code == "provider_input_format_invalid"


def test_fal_submission_uses_official_queue_schema_and_returns_request_id(tmp_path: Path) -> None:
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"image")
    adapter = object.__new__(FalQueueRendererAdapter)
    adapter.api_key = "not-logged"
    adapter.queue_base_url = "https://queue.fal.run"
    adapter.timeout_seconds = 120
    captured = {}

    def fake_request(method, url, *, headers, payload=None, timeout=None):
        captured.update({"method": method, "url": url, "headers": headers, "payload": payload})
        return {"request_id": "fal-request-1"}

    adapter._json_request = fake_request  # type: ignore[method-assign]
    state = adapter.submit(
        model_key="fal-ai/wan/v2.2-5b/image-to-video",
        request_payload={
            "duration_seconds": "5",
            "fps": 24,
            "request_metadata": {"approved_prompt": "A slow reviewed product camera move"},
        },
        input_paths=[image],
    )
    assert state.provider_job_id == "fal-request-1"
    assert captured["url"] == "https://queue.fal.run/fal-ai/wan/v2.2-5b/image-to-video"
    assert captured["headers"]["Authorization"].startswith("Key ")
    assert captured["payload"]["image_url"].startswith("data:image/jpeg;base64,")
    assert captured["payload"]["num_frames"] == 121
    assert captured["payload"]["frames_per_second"] == 24
    assert captured["payload"]["enable_safety_checker"] is True


def test_vidu_submission_and_state_capture_task_credits(tmp_path: Path) -> None:
    image = tmp_path / "frame.webp"
    image.write_bytes(b"image")
    adapter = object.__new__(ViduRendererAdapter)
    adapter.api_key = "not-logged"
    adapter.base_url = "https://api.vidu.com"
    adapter.timeout_seconds = 120
    adapter.usd_per_credit = Decimal("0.10")
    captured = {}

    def fake_request(method, url, *, headers, payload=None, timeout=None):
        captured.update({"method": method, "url": url, "headers": headers, "payload": payload})
        return {"task_id": "vidu-task-1", "state": "created", "credits": 2}

    adapter._json_request = fake_request  # type: ignore[method-assign]
    state = adapter.submit(
        model_key="viduq3-pro-fast",
        request_payload={
            "duration_seconds": 5,
            "request_metadata": {"approved_prompt": "A reviewed camera orbit"},
        },
        input_paths=[image],
    )
    assert state.provider_job_id == "vidu-task-1"
    assert state.credits == Decimal("2")
    assert state.actual_cost_usd == Decimal("0.20")
    assert captured["url"] == "https://api.vidu.com/ent/v2/img2video"
    assert captured["headers"]["Authorization"].startswith("Token ")
    assert captured["payload"]["images"][0].startswith("data:image/webp;base64,")
    assert captured["payload"]["off_peak"] is False


def test_cost_fallback_never_exceeds_or_understates_known_provider_cost() -> None:
    job = {"reserved_cost_usd": "3.50", "estimated_cost_usd": "2.00"}
    assert ProviderManagedWorker._cost_or_conservative_ceiling(job, None) == Decimal("3.50")
    assert ProviderManagedWorker._cost_or_conservative_ceiling(job, Decimal("1.75")) == Decimal("1.75")


def test_worker_is_restart_safe_spend_gated_and_pending_review_only() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "PROVIDER_PAID_EXECUTION_ENABLED" in source
    assert "GenerationJobType.PREMIUM_CLIP" in source
    assert "providers=(self.provider,)" in source
    assert "_existing_provider_job_id" in source
    assert "_record_provider_request" in source
    assert "shared_artifact_version_id" in source
    assert '"review_status": "pending"' in source
    assert '"automatic_approval": False' in source
    assert '"automatic_publishing": False' in source
    assert "'internal_only'" in source
    assert "jobs.complete" in source
    assert "jobs.fail" in source


def test_workers_have_no_login_keys_and_only_internal_producer_role() -> None:
    source = ONBOARDING.read_text(encoding="utf-8")
    assert '"fal-worker"' in source
    assert '"vidu-worker"' in source
    assert "api_key_created" in source
    assert "False" in source
    assert "VALUES (%s,'producer',%s)" in source
    assert '"can_approve": False' in source
    assert '"can_publish": False' in source


def test_setup_stores_secrets_outside_files_and_never_generates() -> None:
    source = SETUP.read_text(encoding="utf-8")
    assert 'SetEnvironmentVariable($Name, $plain, "User")' in source
    assert 'SetEnvironmentVariable($Name, $plain, "Process")' in source
    assert 'values["FAL_KEY"]' not in source
    assert 'values["VIDU_API_KEY"]' not in source
    assert 'pricing = @{ per_second_usd = [string]$PricePerSecond }' in source
    assert 'status = "degraded"' in source
    assert "No generation or credit spend was triggered during setup" in source
    assert "/img2video" not in source
    assert "queue.fal.run/" not in source


def test_provider_supervisor_is_explicit_and_cannot_approve_or_publish() -> None:
    source = SUPERVISOR.read_text(encoding="utf-8")
    assert "PROVIDER_PAID_EXECUTION_ENABLED" in source
    assert "FAL_RENDERER_ENABLED" in source
    assert "VIDU_RENDERER_ENABLED" in source
    assert "src.operations.provider_managed_worker" in source
    assert "automatic_spend_approval = $false" in source
    assert "automatic_creative_approval = $false" in source
    assert "automatic_publishing = $false" in source


def test_runbook_requires_preflight_spend_reservation_and_human_review() -> None:
    source = DOC.read_text(encoding="utf-8")
    assert "renderer preflight and exact quote" in source
    assert "human spend decision" in source
    assert "spend reservation" in source
    assert "pending human review" in source
    assert "Automatic spend approval, creative approval and public publishing remain disabled" in source
