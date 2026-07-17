"""Auditable operator selection of generated P68 clip variants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.p68_job_state import atomic_write_json, utc_now


SELECTION_VERSION = "p68.clip_selection.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_candidates(
    candidate_manifest_path: Path,
    selections: dict[str, int],
    *,
    reviewer: str,
    note: str = "",
    output_path: Path | None = None,
) -> dict[str, Any]:
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if not selections:
        raise ValueError("at least one shot selection is required")
    candidates_payload = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    candidates = candidates_payload.get("candidates") or []
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for item in candidates:
        key = (str(item.get("shot_id") or ""), int(item.get("variant") or 0))
        if key in by_key:
            raise ValueError(f"duplicate candidate: {key[0]} variant {key[1]}")
        by_key[key] = item

    selected = []
    for shot_id, variant in selections.items():
        item = by_key.get((shot_id, variant))
        if item is None:
            raise ValueError(f"candidate does not exist: {shot_id} variant {variant}")
        path = Path(str(item.get("path") or ""))
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_digest = str(item.get("output_sha256") or "")
        if expected_digest and _sha256(path) != expected_digest:
            raise ValueError(f"candidate digest changed: {shot_id} variant {variant}")
        selected.append(
            {
                **item,
                "human_review_status": "approved_for_assembly",
                "selection_scope": "review_assembly_only",
                "selected_by": reviewer.strip(),
                "selected_at": utc_now(),
                "selection_note": note.strip(),
                "preview_only": False,
                "quality_approved": False,
                "publish_allowed": False,
            }
        )

    available_shots = {str(item.get("shot_id")) for item in candidates}
    selected_shots = set(selections)
    payload = {
        "schema_version": SELECTION_VERSION,
        "pilot_id": candidates_payload.get("pilot_id"),
        "candidate_manifest_path": str(candidate_manifest_path),
        "selected_clips": sorted(selected, key=lambda item: str(item["shot_id"])),
        "selection_complete_for_available_shots": available_shots == selected_shots,
        "unselected_available_shot_ids": sorted(available_shots - selected_shots),
        "quality_approved": False,
        "publish_allowed": False,
    }
    target = output_path or candidate_manifest_path.with_name("selection-manifest.json")
    atomic_write_json(target, payload)
    return {**payload, "selection_manifest_path": str(target)}
