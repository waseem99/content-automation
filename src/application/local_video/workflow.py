from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LocalVideoWorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedWorkflow:
    path: Path
    document: dict[str, Any]
    workflow_sha256: str
    checkpoint_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_workflow(
    *,
    workflow_root: Path,
    relative_path: str,
    expected_workflow_sha256: str,
    checkpoint_path: Path,
    expected_checkpoint_sha256: str,
) -> VerifiedWorkflow:
    root = workflow_root.resolve(strict=True)
    path = (root / relative_path).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LocalVideoWorkflowError("workflow_path_outside_approved_root") from exc
    if path.suffix.lower() != ".json":
        raise LocalVideoWorkflowError("workflow_must_be_json")
    actual_workflow = _sha256(path)
    if actual_workflow != expected_workflow_sha256:
        raise LocalVideoWorkflowError("workflow_hash_mismatch")
    checkpoint = checkpoint_path.resolve(strict=True)
    actual_checkpoint = _sha256(checkpoint)
    if actual_checkpoint != expected_checkpoint_sha256:
        raise LocalVideoWorkflowError("checkpoint_hash_mismatch")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalVideoWorkflowError("workflow_json_invalid") from exc
    if not isinstance(document, dict) or not document:
        raise LocalVideoWorkflowError("workflow_json_must_be_object")
    return VerifiedWorkflow(
        path=path,
        document=document,
        workflow_sha256=actual_workflow,
        checkpoint_sha256=actual_checkpoint,
    )
