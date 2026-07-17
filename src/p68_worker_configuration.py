"""Secret-safe configuration readiness for P68 keyframe and video workers."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from src.p68_job_state import atomic_write_json


CONFIGURATION_VERSION = "p68.worker_configuration.v1"
DEPLOY_KEYS = (
    "COMFYUI_REF",
    "WAN22_REVISION",
    "WAN21_REVISION",
    "RN_MODEL_DIR",
    "RN_OUTPUT_DIR",
    "RN_INPUT_DIR",
)


def _present(environ: Mapping[str, str], key: str) -> bool:
    return bool(str(environ.get(key) or "").strip())


def _positive_decimal_present(environ: Mapping[str, str], *keys: str) -> bool:
    value = next((str(environ.get(key) or "").strip() for key in keys if _present(environ, key)), "")
    if not value:
        return False
    try:
        return Decimal(value) > 0
    except (InvalidOperation, ValueError):
        return False


def build_worker_configuration(environ: Mapping[str, str]) -> dict[str, Any]:
    """Return readiness booleans without serializing any configuration values."""

    keyframe_endpoint = _present(environ, "P68_KEYFRAME_BASE_URL") or _present(environ, "P68_RN_BASE_URL")
    keyframe_bearer = _present(environ, "P68_KEYFRAME_BEARER_TOKEN") or _present(environ, "P68_RN_BEARER_TOKEN")
    keyframe_rate = _positive_decimal_present(environ, "P68_KEYFRAME_GPU_HOURLY_USD", "P68_RN_GPU_HOURLY_USD")
    keyframe = {
        "endpoint_present": keyframe_endpoint,
        "checkpoint_present": _present(environ, "P68_KEYFRAME_CHECKPOINT"),
        "license_type_present": _present(environ, "P68_KEYFRAME_MODEL_LICENSE_TYPE"),
        "license_url_present": _present(environ, "P68_KEYFRAME_MODEL_LICENSE_URL"),
        "bearer_token_present": keyframe_bearer,
        "positive_gpu_rate_present": keyframe_rate,
    }
    keyframe["application_ready"] = all(
        keyframe[key]
        for key in (
            "endpoint_present",
            "checkpoint_present",
            "license_type_present",
            "license_url_present",
            "positive_gpu_rate_present",
        )
    )

    video = {
        "endpoint_present": _present(environ, "P68_RN_BASE_URL"),
        "bearer_token_present": _present(environ, "P68_RN_BEARER_TOKEN"),
        "positive_gpu_rate_present": _positive_decimal_present(environ, "P68_RN_GPU_HOURLY_USD"),
        "workflow_path_present": _present(environ, "P68_RN_WORKFLOW"),
    }
    video["application_ready"] = all(
        video[key]
        for key in ("endpoint_present", "positive_gpu_rate_present", "workflow_path_present")
    )

    deployment = {key: _present(environ, key) for key in DEPLOY_KEYS}
    deployment_ready = all(deployment.values())

    if keyframe["application_ready"]:
        next_gate = "run_private_keyframe_worker_health_check"
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
