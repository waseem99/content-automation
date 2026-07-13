"""Atomic, resumable state for P68 media-production jobs."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = "p68.production_job.v1"
STAGE_ORDER = ("validate", "assets", "motion", "assemble", "quality")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def new_state(pilot_id: str, input_digest: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": STATE_VERSION,
        "pilot_id": pilot_id,
        "input_digest": input_digest,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "stages": {stage: {"status": "pending", "attempts": 0} for stage in STAGE_ORDER},
        "publish_allowed": False,
    }


def load_or_create(path: Path, pilot_id: str, input_digest: str) -> dict[str, Any]:
    if not path.is_file():
        state = new_state(pilot_id, input_digest)
        atomic_write_json(path, state)
        return state
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != STATE_VERSION or state.get("pilot_id") != pilot_id:
        raise ValueError(f"Unsupported or mismatched job state: {path}")
    if state.get("input_digest") != input_digest:
        state = new_state(pilot_id, input_digest)
        state["supersedes_input_digest"] = json.loads(path.read_text(encoding="utf-8")).get("input_digest")
        atomic_write_json(path, state)
    return state


def stage_complete(state: dict[str, Any], stage: str, fingerprint: str) -> bool:
    record = state["stages"][stage]
    return record.get("status") == "complete" and record.get("fingerprint") == fingerprint


def start_stage(path: Path, state: dict[str, Any], stage: str) -> None:
    record = state["stages"][stage]
    record.update(
        {
            "status": "running",
            "attempts": int(record.get("attempts") or 0) + 1,
            "started_at": utc_now(),
        }
    )
    record.pop("error", None)
    state["status"] = "running"
    state["updated_at"] = utc_now()
    atomic_write_json(path, state)


def finish_stage(
    path: Path,
    state: dict[str, Any],
    stage: str,
    fingerprint: str,
    outputs: dict[str, Any],
) -> None:
    state["stages"][stage].update(
        {
            "status": "complete",
            "completed_at": utc_now(),
            "fingerprint": fingerprint,
            "outputs": outputs,
        }
    )
    state["status"] = "complete" if stage == STAGE_ORDER[-1] else "running"
    state["updated_at"] = utc_now()
    atomic_write_json(path, state)


def fail_stage(path: Path, state: dict[str, Any], stage: str, error: Exception) -> None:
    state["stages"][stage].update(
        {"status": "failed", "failed_at": utc_now(), "error": f"{type(error).__name__}: {error}"}
    )
    state["status"] = "failed"
    state["updated_at"] = utc_now()
    atomic_write_json(path, state)


def reset_from_stage(path: Path, state: dict[str, Any], stage: str) -> None:
    """Invalidate a stage and every downstream stage, preserving attempt history."""
    start = STAGE_ORDER.index(stage)
    for name in STAGE_ORDER[start:]:
        record = state["stages"][name]
        state["stages"][name] = {
            "status": "pending",
            "attempts": int(record.get("attempts") or 0),
            "invalidated_at": utc_now(),
        }
    state["status"] = "pending"
    state["updated_at"] = utc_now()
    atomic_write_json(path, state)
