from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p36_review_packet import (
    BLOCKER_TYPES,
    CHECKLIST_GATES,
    DECISION_OPTIONS,
    ITEM_TYPES,
    SECTIONS,
    build_blocker_appendix,
    build_local_handoff_manifest,
    build_packet_index,
    build_packet_item,
    build_reviewer_checklist,
    validate_review_packet,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p36-review-packet-example.json")
CHECKLIST_PATH = Path("docs/operations/p36-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p36-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p36-step-01.md"),
    Path("docs/operations/p36-step-02.md"),
    Path("docs/operations/p36-step-03.md"),
    Path("docs/operations/p36-step-04.md"),
    Path("docs/operations/p36-step-05.md"),
    Path("docs/operations/p36-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _item(item_id: str, path: str, item_type: str, section: str, *, required: bool = True) -> dict:
    return build_packet_item(
        item_id,
        f"Item {item_id}",
        path,
        item_type,
        source_system="p36-test",
        source_issue=459,
        review_status="review_required",
        reviewer_role="operator",
        required=required,
        checksum_digest="abc123",
        section=section,
    )


def test_p36_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p36-step-01.md": ["Closes #460", "review packet item metadata", "item_id"],
        "docs/operations/p36-step-02.md": ["Closes #461", "packet index", "executive_summary"],
        "docs/operations/p36-step-03.md": ["Closes #462", "reviewer checklist", "final_operator_decision"],
        "docs/operations/p36-step-04.md": ["Closes #463", "blocker appendix", "unsafe_publish_state"],
        "docs/operations/p36-step-05.md": ["Closes #464", "handoff manifest", "local_only_not_sent"],
        "docs/operations/p36-step-06.md": ["Closes #465", "P36", "no ZIP/archive generation"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_packet_item_supports_all_item_types_and_guardrails() -> None:
    for item_type in ITEM_TYPES:
        item = _item(f"item-{item_type}", f"items/{item_type}.json", item_type, "reference_artifacts")
        assert item["item_type"] == item_type
        assert item["local_only"] is True
        assert item["external_upload"] is False
        assert item["publish_allowed"] is False
        assert item["review_required"] is True


def test_packet_item_rejects_bad_type_and_section() -> None:
    with pytest.raises(ValueError):
        _item("bad-type", "bad.json", "not-supported", "reference_artifacts")
    with pytest.raises(ValueError):
        _item("bad-section", "bad.json", "report", "not-a-section")


def test_packet_index_orders_items_and_counts_sections() -> None:
    items = [
        _item("blocked", "z-blocked.json", "blocker_appendix", "blocked"),
        _item("summary", "a-summary.md", "summary", "executive_summary"),
        _item("ready", "ready.json", "artifact", "ready_for_approval", required=False),
        _item("review", "review.json", "report", "review_required"),
    ]
    packet = build_packet_index("packet-001", "Review Packet", items, generated_at="manual")

    assert packet["schema_version"] == "p36.local_review_packet.v1"
    assert [item["section"] for item in packet["items"]] == ["executive_summary", "review_required", "ready_for_approval", "blocked"]
    assert packet["counts"]["total_items"] == 4
    assert packet["counts"]["required_items"] == 3
    assert packet["counts"]["section_counts"]["blocked"] == 1
    assert packet["counts"]["type_counts"]["artifact"] == 1
    assert packet["local_only"] is True
    assert packet["zip_created"] is False


def test_packet_validation_catches_guardrail_regressions() -> None:
    packet = build_packet_index("packet-002", "Packet", [_item("a", "a.json", "report", "review_required")])
    valid = validate_review_packet(packet)
    packet["external_upload"] = True
    invalid = validate_review_packet(packet)

    assert valid["is_valid"] is True
    assert invalid["is_valid"] is False
    assert "external_upload must remain false" in invalid["errors"]


def test_reviewer_checklist_has_required_gates_and_decisions() -> None:
    checklist = build_reviewer_checklist("checklist-001", "operator", ["item-1", "item-2"])

    assert checklist["gates"] == list(CHECKLIST_GATES)
    assert checklist["decision_options"] == list(DECISION_OPTIONS)
    assert checklist["required_items"] == ["item-1", "item-2"]
    assert checklist["approval_allowed"] is False
    assert checklist["approval_mode"] == "human_only_local_review"
    assert checklist["publish_allowed"] is False


def test_blocker_appendix_counts_supported_types_and_severities() -> None:
    blockers = [
        {
            "blocker_type": "governance_block",
            "severity": "high",
            "source_item_id": "item-1",
            "source_issue": 459,
            "current_status": "blocked",
            "required_resolution": "Resolve governance review.",
            "owner_role": "operator",
            "reviewer_notes": "Manual review required.",
        },
        {
            "blocker_type": "integrity_drift",
            "severity": "medium",
            "source_item_id": "item-2",
            "source_issue": 459,
            "current_status": "review_required",
            "required_resolution": "Confirm checksum drift.",
            "owner_role": "integrity_reviewer",
            "reviewer_notes": "No remediation performed.",
        },
    ]
    appendix = build_blocker_appendix("appendix-001", blockers)

    assert set(BLOCKER_TYPES) >= {item["blocker_type"] for item in appendix["blockers"]}
    assert appendix["severity_counts"]["high"] == 1
    assert appendix["severity_counts"]["medium"] == 1
    assert appendix["type_counts"]["governance_block"] == 1
    assert appendix["automated_remediation_performed"] is False
    assert appendix["deletion_performed"] is False
    assert appendix["publish_allowed"] is False


def test_blocker_appendix_rejects_bad_type_and_severity() -> None:
    with pytest.raises(ValueError):
        build_blocker_appendix("bad", [{"blocker_type": "bad", "severity": "high", "source_item_id": "x"}])
    with pytest.raises(ValueError):
        build_blocker_appendix("bad", [{"blocker_type": "governance_block", "severity": "extreme", "source_item_id": "x"}])


def test_local_handoff_manifest_is_local_only_not_sent() -> None:
    items = [_item("summary", "summary.md", "summary", "executive_summary")]
    packet = build_packet_index("packet-handoff", "Packet", items)
    checklist = build_reviewer_checklist("checklist-handoff", "operator", ["summary"])
    appendix = build_blocker_appendix("appendix-empty", [])
    manifest = build_local_handoff_manifest("manifest-001", packet, [checklist], [appendix])

    assert manifest["schema_version"] == "p36.local_review_handoff.v1"
    assert manifest["packet_id"] == "packet-handoff"
    assert manifest["packet_files"] == ["summary.md"]
    assert manifest["reviewer_roles"] == ["operator"]
    assert manifest["checklist_ids"] == ["checklist-handoff"]
    assert manifest["blocker_appendices"] == ["appendix-empty"]
    assert manifest["distribution_status"] == "local_only_not_sent"
    assert manifest["external_action_performed"] is False
    assert manifest["email_sent"] is False
    assert manifest["slack_sent"] is False
    assert manifest["external_upload"] is False
    assert manifest["publish_allowed"] is False


def test_example_and_closeout_guardrails() -> None:
    example = _read_json(EXAMPLE_PATH)
    checklist = _read_json(CHECKLIST_PATH)
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert example["schema_version"] == "p36.local_review_packet_example.v1"
    assert example["distribution_status"] == "local_only_not_sent"
    assert example["guardrails"]["zip_created"] is False
    assert example["guardrails"]["publish_allowed"] is False
    for issue in ["#460", "#461", "#462", "#463", "#464", "#465"]:
        assert issue in report
    for guardrail in [
        "No ZIP/archive generation.",
        "No email/Slack delivery.",
        "No cloud sync.",
        "No external upload.",
        "No network calls.",
        "No schedulers or background jobs.",
        "No credential storage.",
        "No platform edits.",
        "No deletion or movement.",
        "No auto-publish path.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]
    assert [task["issue"] for task in checklist["child_tasks"]] == [460, 461, 462, 463, 464, 465]
