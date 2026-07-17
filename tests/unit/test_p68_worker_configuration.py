from __future__ import annotations

import json

from src.p68_worker_configuration import build_worker_configuration, sanitized_json


def test_empty_configuration_names_the_private_worker_gate() -> None:
    result = build_worker_configuration({})

    assert result["keyframe_worker"]["application_ready"] is False
    assert result["natural_video_worker"]["application_ready"] is False
    assert result["deployment_configuration_ready"] is False
    assert result["next_gate"] == "configure_private_comfyui_worker"
    assert result["secret_values_serialized"] is False
    assert result["provider_calls_made"] == 0
    assert result["paid_provider_calls_made"] == 0
    assert result["publish_allowed"] is False


def test_ready_remote_keyframe_configuration_serializes_presence_only() -> None:
    env = {
        "P68_KEYFRAME_BASE_URL": "https://private.example.invalid",
        "P68_KEYFRAME_CHECKPOINT": "secret-checkpoint.safetensors",
        "P68_KEYFRAME_MODEL_LICENSE_TYPE": "commercial-license",
        "P68_KEYFRAME_MODEL_LICENSE_URL": "https://license.example.invalid/private",
        "P68_KEYFRAME_BEARER_TOKEN": "super-secret-token",
        "P68_KEYFRAME_GPU_HOURLY_USD": "1.25",
        "P68_RN_WORKFLOW": "private-workflow.json",
    }
    result = build_worker_configuration(env)
    rendered = sanitized_json(env)

    assert result["keyframe_worker"] == {
        "endpoint_present": True,
        "endpoint_is_loopback": False,
        "checkpoint_present": True,
        "license_type_present": True,
        "license_url_present": True,
        "bearer_token_present": True,
        "gpu_rate_record_present": True,
        "gpu_rate_record_valid": True,
        "local_preview_mode": False,
        "application_ready": True,
    }
    assert result["next_gate"] == "run_private_keyframe_worker_health_check"
    for secret in env.values():
        assert secret not in rendered
    json.loads(rendered)


def test_explicit_zero_cost_loopback_preview_is_ready() -> None:
    env = {
        "P68_KEYFRAME_BASE_URL": "http://127.0.0.1:8188",
        "P68_KEYFRAME_CHECKPOINT": "sd_xl_base_1.0.safetensors",
        "P68_KEYFRAME_MODEL_LICENSE_TYPE": "CreativeML-Open-RAIL++-M",
        "P68_KEYFRAME_MODEL_LICENSE_URL": "https://license.example.invalid",
        "P68_KEYFRAME_GPU_HOURLY_USD": "0.00",
        "P68_KEYFRAME_EXECUTION_MODE": "local_preview",
    }
    result = build_worker_configuration(env)

    assert result["keyframe_worker"]["endpoint_is_loopback"] is True
    assert result["keyframe_worker"]["local_preview_mode"] is True
    assert result["keyframe_worker"]["gpu_rate_record_valid"] is True
    assert result["keyframe_worker"]["application_ready"] is True
    assert result["next_gate"] == "run_local_keyframe_sample"
    assert result["paid_provider_calls_made"] == 0
    assert result["publish_allowed"] is False


def test_zero_cost_remote_or_invalid_rate_is_not_ready() -> None:
    base = {
        "P68_KEYFRAME_BASE_URL": "https://worker.invalid",
        "P68_KEYFRAME_CHECKPOINT": "checkpoint.safetensors",
        "P68_KEYFRAME_MODEL_LICENSE_TYPE": "license",
        "P68_KEYFRAME_MODEL_LICENSE_URL": "http://license.invalid",
    }
    for rate in ("", "0", "-1", "not-a-number"):
        result = build_worker_configuration({**base, "P68_KEYFRAME_GPU_HOURLY_USD": rate})
        assert result["keyframe_worker"]["gpu_rate_record_valid"] is False
        assert result["keyframe_worker"]["application_ready"] is False
