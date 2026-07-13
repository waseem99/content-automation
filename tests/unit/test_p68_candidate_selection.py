from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.p68_candidate_selection import select_candidates


def manifest(tmp_path: Path) -> Path:
    candidates = []
    for variant in (1, 2):
        clip = tmp_path / f"S01-v{variant}.mp4"
        clip.write_bytes(f"clip-{variant}".encode())
        candidates.append(
            {
                "shot_id": "S01",
                "variant": variant,
                "path": str(clip),
                "output_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
                "provider": "rn-comfyui-wan",
                "prompt_or_asset_reference": "prompt_sha256:test",
                "rights_status": "generated_for_project",
            }
        )
    path = tmp_path / "candidate-manifest.json"
    path.write_text(json.dumps({"pilot_id": "pilot", "candidates": candidates}), encoding="utf-8")
    return path


def test_selects_existing_digest_verified_variant_for_assembly_only(tmp_path: Path) -> None:
    result = select_candidates(manifest(tmp_path), {"S01": 2}, reviewer="editor", note="best motion")
    selected = result["selected_clips"][0]
    assert selected["variant"] == 2
    assert selected["human_review_status"] == "approved_for_assembly"
    assert selected["quality_approved"] is False
    assert selected["publish_allowed"] is False
    assert result["selection_complete_for_available_shots"] is True


def test_rejects_unknown_or_changed_candidate(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        select_candidates(path, {"S01": 3}, reviewer="editor")
    (tmp_path / "S01-v1.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest changed"):
        select_candidates(path, {"S01": 1}, reviewer="editor")
