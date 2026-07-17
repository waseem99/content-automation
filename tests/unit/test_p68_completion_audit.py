from __future__ import annotations

import json
from pathlib import Path

from src.p68_completion_audit import build_completion_audit, write_completion_audit


ROOT = Path(__file__).resolve().parents[2]


def test_clean_clone_audit_names_every_unfinished_shot(tmp_path: Path) -> None:
    result = build_completion_audit(ROOT / "p68-pilots", tmp_path, environ={})

    assert result["pilot_count"] == 6
    assert result["roster_complete"] is True
    assert result["specs_ready"] is True
    assert result["totals"] == {
        "total_shots": 36,
        "authored_science_shots": 7,
        "authored_science_ready": 0,
        "natural_motion_shots": 29,
        "keyframes_approved": 0,
        "keyframes_pending_review": 0,
        "keyframes_missing": 29,
        "candidate_shots_available": 0,
        "selected_natural_shots": 0,
        "hybrid_review_renders_ready": 0,
    }
    assert len(result["execution_queue"]) == 36
    assert result["next_gate"] == "create_and_review_shot_specific_keyframes"
    assert result["external_execution_required"] is True
    assert result["provider_calls_made"] == 0
    assert result["paid_provider_calls_made"] == 0
    assert result["vercel_deployment_required"] is False
    assert result["production_candidate_count"] == 0
    assert result["publish_allowed"] is False


def test_audit_advances_real_local_artifacts_without_claiming_approval(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "gold" / "rawr-blind-spot"
    generated_assets = artifact_dir / "generated-assets"
    generated_assets.mkdir(parents=True)
    keyframe = generated_assets / "s01-keyframe-v1.png"
    keyframe.write_bytes(b"reviewed-keyframe")
    (generated_assets / "keyframe-provenance.json").write_text(
        json.dumps(
            {
                "shots": {
                    "S01": {
                        "normalized_path": str(keyframe),
                        "human_review_status": "approved_for_generation",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (generated_assets / "shot-keyframes.json").write_text(
        json.dumps({"shots": {"S01": {"approved_for_generation": True}}}),
        encoding="utf-8",
    )

    science_dir = artifact_dir / "clips" / "scientific-v5"
    science_dir.mkdir(parents=True)
    (science_dir / "S02.mp4").write_bytes(b"authored-science")

    result = build_completion_audit(
        ROOT / "p68-pilots",
        tmp_path,
        environ={
            "P68_RN_BASE_URL": "https://private-worker.invalid",
            "P68_RN_GPU_HOURLY_USD": "1.00",
        },
    )
    blind_spot = next(item for item in result["pilots"] if item["pilot_id"] == "rawr-blind-spot")
    shots = {item["shot_id"]: item for item in blind_spot["shots"]}

    assert shots["S01"]["status"] == "approved_keyframe_ready_for_rn"
    assert shots["S01"]["next_action"] == "submit_bounded_rn_generation"
    assert shots["S02"]["status"] == "ready_for_assembly"
    assert result["totals"]["keyframes_approved"] == 1
    assert result["totals"]["authored_science_ready"] == 1
    assert result["production_candidate_count"] == 0
    assert result["publish_allowed"] is False


def test_writer_emits_json_and_markdown_reports(tmp_path: Path) -> None:
    output = tmp_path / "audit" / "p68-completion.json"
    result = write_completion_audit(ROOT / "p68-pilots", tmp_path / "artifacts", output, environ={})

    assert output.is_file()
    report = output.with_suffix(".md")
    assert report.is_file()
    assert "P68 Six-Pilot Completion Audit" in report.read_text(encoding="utf-8")
    assert result["json_path"] == str(output)
    assert result["report_path"] == str(report)
