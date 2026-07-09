from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p34_artifacts import (
    P34_MANIFEST_VERSION,
    build_materialized_manifest,
    build_operator_summary,
    materialize_command_result,
    validate_artifact_path,
    write_json_artifact,
    write_operator_summary,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p34-artifact-writer-example.json")
CHECKLIST_PATH = Path("docs/operations/p34-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p34-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p34-step-01.md"),
    Path("docs/operations/p34-step-02.md"),
    Path("docs/operations/p34-step-03.md"),
    Path("docs/operations/p34-step-04.md"),
    Path("docs/operations/p34-step-05.md"),
    Path("docs/operations/p34-step-06.md"),
]


def _sample_payload() -> dict:
    return {
        "schema_version": "p33.safe_local_cli_result.v1",
        "command_name": "validate-package",
        "mode": "validate",
        "status": "success",
        "warnings": ["review_required"],
        "blockers": [],
        "planned_outputs": ["reports/local/validation_report.json"],
        "publish_allowed": False,
        "review_required": True,
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p34_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p34-step-01.md": ["Closes #444", "path validation", "Reject absolute paths"],
        "docs/operations/p34-step-02.md": ["Closes #445", "JSON artifact writer", "no-overwrite"],
        "docs/operations/p34-step-03.md": ["Closes #446", "operator summary writer", "review-required"],
        "docs/operations/p34-step-04.md": ["Closes #447", "manifest", "written_files"],
        "docs/operations/p34-step-05.md": ["Closes #448", "overwrite-safety", "allow_overwrite=True"],
        "docs/operations/p34-step-06.md": ["Closes #449", "P34", "no external upload"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_validate_artifact_path_allows_nested_safe_paths(tmp_path: Path) -> None:
    result = validate_artifact_path(tmp_path, "nested/result.json")

    assert result["status"] == "allowed"
    assert Path(result["resolved_path"]).is_relative_to(tmp_path.resolve())
    assert result["local_only"] is True
    assert result["external_upload"] is False
    assert result["publish_allowed"] is False


@pytest.mark.parametrize(
    "artifact_name",
    [
        "/tmp/result.json",
        "../result.json",
        "nested/../result.json",
        "~/result.json",
        "https://example.com/result.json",
        "file:///tmp/result.json",
        "bad\\path.json",
        " padded.json",
    ],
)
def test_validate_artifact_path_blocks_unsafe_paths(tmp_path: Path, artifact_name: str) -> None:
    result = validate_artifact_path(tmp_path, artifact_name)

    assert result["status"] == "blocked"
    assert result["artifact_name"] == artifact_name
    assert result["external_upload"] is False
    assert result["publish_allowed"] is False


def test_write_json_artifact_is_deterministic_and_local_only(tmp_path: Path) -> None:
    result = write_json_artifact(tmp_path, "out/result.json", {"b": 2, "a": 1})
    path = Path(result["path"])

    assert result["status"] == "written"
    assert result["content_type"] == "application/json"
    assert path.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "b": 2\n}\n'
    assert result["external_upload"] is False
    assert result["cloud_sync"] is False
    assert result["network_called"] is False


def test_write_operator_summary_contains_guardrails(tmp_path: Path) -> None:
    result = write_operator_summary(tmp_path, "out/operator_summary.md", _sample_payload())
    content = Path(result["path"]).read_text(encoding="utf-8")

    assert result["status"] == "written"
    assert "Operator Summary — validate-package" in content
    assert "No external upload" in content
    assert "Human review remains required" in content
    assert result["content_type"] == "text/markdown"


def test_build_operator_summary_handles_empty_lists() -> None:
    content = build_operator_summary({"command_name": "build-report", "status": "success", "mode": "inspect"})

    assert "Operator Summary — build-report" in content
    assert "- None" in content
    assert "Local-only review artifact" in content


def test_build_materialized_manifest_has_required_fields(tmp_path: Path) -> None:
    written = [{"path": str(tmp_path / "result.json"), "status": "written"}]
    blocked = [{"artifact_name": "../bad.json", "status": "blocked", "reason": "parent traversal"}]
    manifest = build_materialized_manifest("validate-package", tmp_path, written, blocked, created_at="2026-07-09T00:00:00Z")

    assert manifest["schema_version"] == P34_MANIFEST_VERSION
    assert manifest["command_name"] == "validate-package"
    assert manifest["written_files"] == written
    assert manifest["blocked_files"] == blocked
    assert manifest["warnings"] == ["parent traversal"]
    assert manifest["local_only"] is True
    assert manifest["review_required"] is True


def test_materialize_command_result_writes_json_summary_and_manifest(tmp_path: Path) -> None:
    manifest = materialize_command_result(tmp_path, _sample_payload(), created_at="2026-07-09T00:00:00Z")

    assert manifest["schema_version"] == P34_MANIFEST_VERSION
    assert manifest["command_name"] == "validate-package"
    assert len(manifest["written_files"]) == 3
    assert manifest["blocked_files"] == []
    assert (tmp_path / "validate-package" / "result.json").exists()
    assert (tmp_path / "validate-package" / "operator_summary.md").exists()
    assert (tmp_path / "validate-package" / "manifest.json").exists()
    assert manifest["external_upload"] is False
    assert manifest["publish_allowed"] is False


def test_overwrite_is_blocked_by_default_and_allowed_explicitly(tmp_path: Path) -> None:
    first = write_json_artifact(tmp_path, "out/result.json", {"a": 1})
    second = write_json_artifact(tmp_path, "out/result.json", {"a": 2})
    third = write_json_artifact(tmp_path, "out/result.json", {"a": 3}, allow_overwrite=True)

    assert first["status"] == "written"
    assert second["status"] == "blocked"
    assert second["reason"] == "target exists and overwrite is not allowed"
    assert third["status"] == "written"
    assert json.loads(Path(third["path"]).read_text(encoding="utf-8"))["a"] == 3


def test_blocked_path_does_not_create_partial_file(tmp_path: Path) -> None:
    result = write_json_artifact(tmp_path, "../escape.json", {"a": 1})

    assert result["status"] == "blocked"
    assert not (tmp_path.parent / "escape.json").exists()


def test_example_file_and_closeout_guardrails() -> None:
    example = _read_json(EXAMPLE_PATH)
    checklist = _read_json(CHECKLIST_PATH)
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert example["schema_version"] == "p34.local_artifact_writer_example.v1"
    assert example["guardrails"]["external_upload"] is False
    assert example["guardrails"]["publish_allowed"] is False
    for issue in ["#444", "#445", "#446", "#447", "#448", "#449"]:
        assert issue in report
    for guardrail in [
        "No external uploads.",
        "No cloud storage sync.",
        "No network calls.",
        "No schedulers or background jobs.",
        "No OAuth or credential storage.",
        "No destructive cleanup.",
        "No platform edits.",
        "No auto-publish path.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]
    assert [task["issue"] for task in checklist["child_tasks"]] == [444, 445, 446, 447, 448, 449]
