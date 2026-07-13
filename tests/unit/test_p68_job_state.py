from __future__ import annotations

import json
from pathlib import Path

from src.p68_job_state import finish_stage, load_or_create, reset_from_stage, stage_complete, start_stage


def test_job_state_checkpoints_and_resumes_completed_stage(tmp_path: Path) -> None:
    path = tmp_path / "job-state.json"
    state = load_or_create(path, "pilot-one", "digest-one")
    start_stage(path, state, "validate")
    finish_stage(path, state, "validate", "fingerprint", {"valid": True})
    resumed = load_or_create(path, "pilot-one", "digest-one")

    assert stage_complete(resumed, "validate", "fingerprint") is True
    assert resumed["stages"]["validate"]["attempts"] == 1
    assert json.loads(path.read_text())["publish_allowed"] is False


def test_changed_inputs_reset_stages_without_losing_previous_digest(tmp_path: Path) -> None:
    path = tmp_path / "job-state.json"
    load_or_create(path, "pilot-one", "digest-one")
    changed = load_or_create(path, "pilot-one", "digest-two")

    assert changed["input_digest"] == "digest-two"
    assert changed["supersedes_input_digest"] == "digest-one"
    assert changed["stages"]["validate"]["status"] == "pending"


def test_reset_invalidates_only_selected_stage_and_downstream(tmp_path: Path) -> None:
    path = tmp_path / "job-state.json"
    state = load_or_create(path, "pilot-one", "digest-one")
    for stage in ("validate", "assets", "motion"):
        start_stage(path, state, stage)
        finish_stage(path, state, stage, f"{stage}-fingerprint", {"stage": stage})

    reset_from_stage(path, state, "motion")

    assert state["stages"]["validate"]["status"] == "complete"
    assert state["stages"]["assets"]["status"] == "complete"
    assert state["stages"]["motion"]["status"] == "pending"
    assert state["stages"]["assemble"]["status"] == "pending"
