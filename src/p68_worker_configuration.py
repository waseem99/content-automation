"""Secret-safe configuration readiness for P68 keyframe and video workers."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from src.p68_job_state import atomic_write_json


CONFIGURATION_VERSION = "p68.worker_configuration.v2"
DEPLOY_KEYS = (
    "COMFYUI_REF",
    "WAN22_REVISION",
    "WAN21_REVISION",
    "RN_MODEL_DIR",
    "RN_OUTPUT_DIR",
    "RN_INPUT_DIR",
)


def _value(environ: Mapping[str, str], key: str) -> str:
    return str(environ.get(key) or "").strip()


def _present(environ: Mapping[str, str], key: str) -> bool:
    return bool(_value(environ, key))


def _decimal(environ: Mapping[str, str], *keys: str) -> tuple[bool, Decimal | None]:
    value = next((_value(environ, key) for key in keys if _present(environ, key)), "")
    if not value:
        return False, None
    try:
        return True, Decimal(value)
    except (InvalidOperation, ValueError):
        return True, None


def _loopback_endpoint(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").lower()
    except ValueError:
        return False
    return host in {"127.0.0.1", "localhost", "::1"}


def build_worker_configuration(environ: Mapping[str, str]) -> dict[str, Any]:
    """Return readiness booleans without serializing any configuration values."""

    keyframe_endpoint_value = _value(environ, "P68_KEYFRAME_BASE_URL") or _value(environ, "P68_RN_BASE_URL")
    keyframe_endpoint = bool(keyframe_endpoint_value)
    keyframe_bearer = _present(environ, "P68_KEYFRAME_BEARER_TOKEN") or _present(environ, "P68_RN_BEARER_TOKEN")
    rate_present, keyframe_rate = _decimal(environ, "P68_KEYFRAME_GPU_HOURLY_USD", "P68_RN_GPU_HOURLY_USD")
    execution_mode = _value(environ, "P68_KEYFRAME_EXECUTION_MODE")
    local_preview = execution_mode == "local_preview" and _loopback_endpoint(keyframe_endpoint_value)
    cost_record_valid = bool(
        rate_present
        and keyframe_rate is not None
        and (keyframe_rate > 0 or (local_preview and keyframe_rate == 0))
    )
    keyframe = {
        "endpoint_present": keyframe_endpoint,
        "endpoint_is_loopback": _loopback_endpoint(keyframe_endpoint_value),
        "checkpoint_present": _present(environ, "P68_KEYFRAME_CHECKPOINT"),
        "license_type_present": _present(environ, "P68_KEYFRAME_MODEL_LICENSE_TYPE"),
        "license_url_present": _present(environ, "P68_KEYFRAME_MODEL_LICENSE_URL"),
        "bearer_token_present": keyframe_bearer,
        "gpu_rate_record_present": rate_present,
        "gpu_rate_record_valid": cost_record_valid,
        "local_preview_mode": local_preview,
    }
    keyframe["application_ready"] = all(
        keyframe[key]
        for key in (
            "endpoint_present",
            "checkpoint_present",
            "license_type_present",
            "license_url_present",
            "gpu_rate_record_valid",
        )
    )

    video_rate_present, video_rate = _decimal(environ, "P68_RN_GPU_HOURLY_USD")
    video = {
        "endpoint_present": _present(environ, "P68_RN_BASE_URL"),
        "bearer_token_present": _present(environ, "P68_RN_BEARER_TOKEN"),
        "positive_gpu_rate_present": bool(video_rate_present and video_rate is not None and video_rate > 0),
        "workflow_path_present": _present(environ, "P68_RN_WORKFLOW"),
    }
    video["application_ready"] = all(
        video[key]
        for key in ("endpoint_present", "positive_gpu_rate_present", "workflow_path_present")
    )

    deployment = {key: _present(environ, key) for key in DEPLOY_KEYS}
    deployment_ready = all(deployment.values())

    if keyframe["application_ready"]:
        next_gate = "run_local_keyframe_sample" if local_preview else "run_private_keyframe_worker_health_check"
    elif deployment_ready:
        next_gate = "deploy_worker_and_record_private_application_endpoint"
    else:
        next_gate = "configure_private_comfyui_worker"

    return {
        "schema_version": CONFIGURATION_VERSION,
        "keyframe_worker": keyframe,
        "natural_video_worker": video,
        "deployment_configuration_presence": deployment,
        "deployment_configuration_ready": deployment_ready,
        "next_gate": next_gate,
        "secret_values_serialized": False,
        "provider_calls_made": 0,
        "paid_provider_calls_made": 0,
        "publish_allowed": False,
    }


def write_worker_configuration(
    environ: Mapping[str, str],
    output_path: str | Path,
) -> dict[str, Any]:
    result = build_worker_configuration(environ)
    atomic_write_json(Path(output_path), result)
    return result


def sanitized_json(environ: Mapping[str, str]) -> str:
    return json.dumps(build_worker_configuration(environ), indent=2)
