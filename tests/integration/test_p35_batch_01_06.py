from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p35_integrity import (
    RETENTION_CLASSES,
    VERIFICATION_STATUSES,
    build_drift_report,
    build_inventory,
    build_inventory_entry,
    build_retention_policy,
    checksum_payload,
    verify_inventory,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p35-integrity-example.json")
CHECKLIST_PATH = Path("docs/operations/p35-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p35-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p35-step-01.md"),
    Path("docs/operations/p35-step-02.md"),
    Path("docs/operations/p35-step-03.md"),
    Path("docs/operations/p35-step-04.md"),
    Path("docs/operations/p35-step-05.md"),
    Path("docs/operations/p35-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry(name: str, path: str, payload: object = "content") -> dict:
    return build_inventory_entry(name, path, payload, source_command="validate-package", generated_at="2026-07-09T00:00:00Z")


def test_p35_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p35-step-01.md": ["Closes #452", "checksum generation", "sha256"],
        "docs/operations/p35-step-02.md": ["Closes #453", "inventory metadata", "artifact_name"],
        "docs/operations/p35-step-03.md": ["Closes #454", "retention policy", "deletion_allowed"],
        "docs/operations/p35-step-04.md": ["Closes #455", "integrity verification", "unexpected"],
        "docs/operations/p35-step-05.md": ["Closes #456", "drift", "advisory"],
        "docs/operations/p35-step-06.md": ["Closes #457", "P35", "no deletion"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_checksum_generation_is_deterministic_for_text_bytes_and_json() -> None:
    text_a = checksum_payload("hello", generated_at="manual")
    text_b = checksum_payload("hello", generated_at="manual")
    bytes_checksum = checksum_payload(b"hello", generated_at="manual")
    json_a = checksum_payload({"b": 2, "a": 1}, generated_at="manual")
    json_b = checksum_payload({"a": 1, "b": 2}, generated_at="manual")

    assert text_a == text_b
    assert text_a["algorithm"] == "sha256"
    assert text_a["content_type"] == "text/plain"
    assert bytes_checksum["content_type"] == "application/octet-stream"
    assert json_a["digest"] == json_b["digest"]
    assert json_a["content_type"] == "application/json"
    assert text_a["deletion_performed"] is False
    assert text_a["publish_allowed"] is False


def test_inventory_entry_and_inventory_are_local_only_and_ordered() -> None:
    entries = [_entry("b", "z/b.json", {"b": 2}), _entry("a", "a/a.json", {"a": 1})]
    inventory = build_inventory(entries, inventory_id="inventory-001", generated_at="manual")

    assert inventory["schema_version"] == "p35.artifact_inventory.v1"
    assert [entry["relative_path"] for entry in inventory["entries"]] == ["a/a.json", "z/b.json"]
    for entry in inventory["entries"]:
        assert entry["checksum"]["algorithm"] == "sha256"
        assert entry["local_only"] is True
        assert entry["review_required"] is True
    assert inventory["guardrails"]["external_upload"] is False
    assert inventory["publish_allowed"] is False


def test_retention_policy_supports_classes_and_never_allows_deletion() -> None:
    for retention_class in RETENTION_CLASSES:
        policy = build_retention_policy(
            f"policy-{retention_class}",
            retention_class,
            review_after_days=30,
            owner_role="operator",
            reason="review intent",
        )
        assert policy["schema_version"] == "p35.retention_policy.v1"
        assert policy["retention_class"] == retention_class
        assert policy["deletion_allowed"] is False
        assert policy["manual_review_required"] is True
        assert policy["deletion_performed"] is False


def test_retention_policy_rejects_unsupported_class() -> None:
    with pytest.raises(ValueError):
        build_retention_policy("bad", "delete_now", review_after_days=0, owner_role="operator", reason="unsafe")


def test_inventory_verification_covers_match_missing_changed_and_unexpected() -> None:
    expected_match = _entry("match", "match.json", {"value": 1})
    expected_missing = _entry("missing", "missing.json", {"value": 2})
    expected_changed = _entry("changed", "changed.json", {"value": 3})
    inventory = build_inventory([expected_match, expected_missing, expected_changed], inventory_id="inventory-verify")
    observed_match = _entry("match", "match.json", {"value": 1})
    observed_changed = _entry("changed", "changed.json", {"value": "changed"})
    observed_unexpected = _entry("unexpected", "unexpected.json", {"value": 4})

    verification = verify_inventory(inventory, [observed_match, observed_changed, observed_unexpected])
    statuses = {item["relative_path"]: item["status"] for item in verification["results"]}

    assert set(VERIFICATION_STATUSES) == {"match", "missing", "changed", "unexpected"}
    assert statuses["match.json"] == "match"
    assert statuses["missing.json"] == "missing"
    assert statuses["changed.json"] == "changed"
    assert statuses["unexpected.json"] == "unexpected"
    assert verification["counts"]["match"] == 1
    assert verification["counts"]["missing"] == 1
    assert verification["counts"]["changed"] == 1
    assert verification["counts"]["unexpected"] == 1
    assert verification["deletion_performed"] is False
    assert verification["external_upload"] is False


def test_drift_report_is_advisory_and_non_destructive() -> None:
    inventory = build_inventory([_entry("a", "a.json", "a")], inventory_id="inventory-drift")
    verification = verify_inventory(inventory, [_entry("a", "a.json", "changed")])
    policy = build_retention_policy("policy-review", "review_later", review_after_days=7, owner_role="operator", reason="manual check")
    report = build_drift_report(verification, [policy], generated_at="manual")

    assert report["schema_version"] == "p35.drift_warning_report.v1"
    assert "changed_artifacts_detected" in report["warnings"]
    assert "manual_review_required:policy-review" in report["warnings"]
    assert "retention_review_required:policy-review" in report["warnings"]
    assert report["cleanup_performed"] is False
    assert report["external_action_performed"] is False
    assert report["deletion_performed"] is False
    assert report["moving_performed"] is False
    assert report["publish_allowed"] is False
    assert any("Do not delete" in step for step in report["next_operator_steps"])


def test_example_and_closeout_guardrails() -> None:
    example = _read_json(EXAMPLE_PATH)
    checklist = _read_json(CHECKLIST_PATH)
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert example["schema_version"] == "p35.local_artifact_integrity_example.v1"
    assert example["retention_policy"]["deletion_allowed"] is False
    assert example["guardrails"]["external_upload"] is False
    assert example["guardrails"]["publish_allowed"] is False
    for issue in ["#452", "#453", "#454", "#455", "#456", "#457"]:
        assert issue in report
    for guardrail in [
        "No deletion.",
        "No moving or archiving files.",
        "No cloud sync.",
        "No external upload.",
        "No network calls.",
        "No schedulers or background jobs.",
        "No credential storage.",
        "No platform edits.",
        "No auto-publish path.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]
    assert [task["issue"] for task in checklist["child_tasks"]] == [452, 453, 454, 455, 456, 457]
