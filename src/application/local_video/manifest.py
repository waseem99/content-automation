from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.application.local_video.workflow import VerifiedWorkflow, verify_workflow


class LocalVideoManifestError(RuntimeError):
    pass


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_PARAMETER_KEYS = {
    "prompt_path",
    "negative_prompt_path",
    "source_image_path",
    "seed_path",
    "width_path",
    "height_path",
    "frame_count_path",
    "fps_path",
    "steps_path",
}


@dataclass(frozen=True)
class ActivatedWorkflow:
    spec: dict[str, Any]
    verified: VerifiedWorkflow
    checkpoint_path: Path


def load_and_verify_manifest(path: Path, *, repository_root: Path) -> list[ActivatedWorkflow]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalVideoManifestError("local_video_manifest_invalid") from exc
    if not isinstance(document, dict):
        raise LocalVideoManifestError("local_video_manifest_must_be_object")
    if document.get("enabled") is not True:
        raise LocalVideoManifestError("local_video_renderer_not_enabled")
    base_url = str(document.get("comfyui_base_url") or "")
    if base_url not in {"http://127.0.0.1:8188", "http://localhost:8188"}:
        raise LocalVideoManifestError("local_video_comfyui_must_be_loopback")

    workflow_root = (repository_root / str(document.get("workflow_root") or "")).resolve()
    checkpoint_root = (repository_root / str(document.get("checkpoint_root") or "")).resolve()
    results: list[ActivatedWorkflow] = []
    seen: set[str] = set()
    for raw in document.get("workflows") or []:
        if not isinstance(raw, dict):
            raise LocalVideoManifestError("local_video_workflow_spec_invalid")
        key = str(raw.get("workflow_key") or "").strip()
        if not key or key in seen:
            raise LocalVideoManifestError("local_video_workflow_key_invalid_or_duplicate")
        seen.add(key)
        workflow_hash = str(raw.get("workflow_sha256") or "")
        checkpoint_hash = str(raw.get("checkpoint_sha256") or "")
        if not _HEX64.fullmatch(workflow_hash) or not _HEX64.fullmatch(checkpoint_hash):
            raise LocalVideoManifestError("local_video_hash_placeholder_or_invalid")
        contract = raw.get("parameter_contract")
        if not isinstance(contract, dict) or set(contract) != _REQUIRED_PARAMETER_KEYS:
            raise LocalVideoManifestError("local_video_parameter_contract_incomplete")
        if any("REPLACE_WITH" in str(value) for value in contract.values()):
            raise LocalVideoManifestError("local_video_parameter_contract_placeholder")
        checkpoint = (checkpoint_root / str(raw.get("checkpoint_relative_path") or "")).resolve()
        try:
            checkpoint.relative_to(checkpoint_root)
        except ValueError as exc:
            raise LocalVideoManifestError("local_video_checkpoint_outside_approved_root") from exc
        verified = verify_workflow(
            workflow_root=workflow_root,
            relative_path=str(raw.get("workflow_relative_path") or ""),
            expected_workflow_sha256=workflow_hash,
            checkpoint_path=checkpoint,
            expected_checkpoint_sha256=checkpoint_hash,
        )
        results.append(ActivatedWorkflow(spec=dict(raw), verified=verified, checkpoint_path=checkpoint))
    if not results:
        raise LocalVideoManifestError("local_video_manifest_has_no_workflows")
    return results
