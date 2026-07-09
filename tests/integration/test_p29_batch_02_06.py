from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p29_governance import (
    REQUIRED_CHECKLIST_SECTIONS,
    REQUIRED_EVIDENCE_FIELDS,
    REVIEW_STATES,
    build_evidence_trail,
    build_human_review_checklist,
    build_p29_closeout_checklist,
    build_publish_readiness_manifests,
    build_render_rules,
    validate_evidence_trail,
    validate_human_review_checklist,
    validate_p29_closeout,
    validate_publish_readiness_manifests,
    validate_render_rules,
)


pytestmark = pytest.mark.integration

DOCS = [
    Path("docs/operations/p29-step-02.md"),
    Path("docs/operations/p29-step-03.md"),
    Path("docs/operations/p29-step-04.md"),
    Path("docs/operations/p29-step-05.md"),
    Path("docs/operations/p29-closeout-report.md"),
]

EXAMPLES = {
    "checklist": Path("docs/operations/p29-human-review-checklist-example.json"),
    "manifest": Path("docs/operations/p29-publish-readiness-manifest-example.json"),
    "render": Path("docs/operations/p29-render-rules-example.json"),
    "evidence": Path("docs/operations/p29-editorial-evidence-example.json"),
    "closeout": Path("docs/operations/p29-closeout-checklist.json"),
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p29_batch_docs_exist_and_reference_child_issues() -> None:
    for path in DOCS:
        assert path.exists(), path

    expected = {
        "docs/operations/p29-step-02.md": ["Closes #363", "script_accuracy", "shorts", "explainer"],
        "docs/operations/p29-step-03.md": ["Closes #364", "content_package_path", "publish_export_ready", "platform export is not the same as actual upload"],
        "docs/operations/p29-step-04.md": ["Closes #365", "preview_video.mp4", "publish_video.mp4", "final_video.mp4"],
        "docs/operations/p29-step-05.md": ["Closes #366", "reviewer", "decision", "Evidence is internal"],
        "docs/operations/p29-closeout-report.md": ["Closes #367", "#363", "#364", "#365", "#366", "#367", "no auto-publish path"],
    }
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_human_review_checklist_contract_and_example_are_valid() -> None:
    generated = build_human_review_checklist()
    example = _read_json(EXAMPLES["checklist"])

    for checklist in (generated, example):
        result = validate_human_review_checklist(checklist)
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert checklist["states"] == list(REVIEW_STATES)
        sections = {section["section"] for section in checklist["sections"]}
        assert set(REQUIRED_CHECKLIST_SECTIONS) <= sections
        assert set(checklist["variants"]) >= {"shorts", "explainer"}
        assert checklist["publish_allowed"] is False
        assert checklist["review_required"] is True


def test_human_review_checklist_catches_missing_sections_and_variants() -> None:
    checklist = build_human_review_checklist()
    checklist["sections"] = [section for section in checklist["sections"] if section["section"] != "music_license"]
    del checklist["variants"]["shorts"]

    result = validate_human_review_checklist(checklist)

    assert result["is_valid"] is False
    assert "required checklist sections missing" in result["errors"]
    assert "review variants missing" in result["errors"]


def test_publish_readiness_manifest_contract_and_example_are_valid() -> None:
    generated = build_publish_readiness_manifests()
    example = _read_json(EXAMPLES["manifest"])

    for manifest in (generated, example):
        result = validate_publish_readiness_manifests(manifest)
        assert result["is_valid"] is True
        assert result["errors"] == []
        states = {item["readiness_state"] for item in manifest["examples"]}
        assert {"not_publish_ready", "review_required", "publish_export_ready"} <= states
        for item in manifest["examples"]:
            assert item["platform_export_is_upload"] is False
        assert manifest["alignment"]["p27_exports_are_not_uploads"] is True
        assert manifest["publish_allowed"] is False


def test_publish_readiness_manifest_catches_upload_regression() -> None:
    manifest = build_publish_readiness_manifests()
    manifest["examples"][0]["platform_export_is_upload"] = True
    manifest["alignment"]["p27_exports_are_not_uploads"] = False

    result = validate_publish_readiness_manifests(manifest)

    assert result["is_valid"] is False
    assert "platform export must not be upload" in result["errors"]
    assert "P27 export upload distinction required" in result["errors"]


def test_render_rules_contract_and_example_are_valid() -> None:
    generated = build_render_rules()
    example = _read_json(EXAMPLES["render"])

    for rules in (generated, example):
        result = validate_render_rules(rules)
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert rules["render_modes"]["preview"]["output_name"] == "preview_video.mp4"
        assert rules["render_modes"]["publish"]["output_name"] == "publish_video.mp4"
        assert rules["readme_mismatch"]["final_video_mp4_is_ambiguous"] is True
        assert rules["publish_allowed"] is False


def test_render_rules_catches_preview_publish_mismatch_regression() -> None:
    rules = build_render_rules()
    rules["render_modes"]["preview"]["output_name"] = "final_video.mp4"
    rules["readme_mismatch"]["final_video_mp4_is_ambiguous"] = False

    result = validate_render_rules(rules)

    assert result["is_valid"] is False
    assert "preview_video.mp4 required" in result["errors"]
    assert "final_video.mp4 mismatch must be recorded" in result["errors"]


def test_evidence_trail_contract_and_example_are_valid() -> None:
    generated = build_evidence_trail()
    example = _read_json(EXAMPLES["evidence"])

    for evidence in (generated, example):
        result = validate_evidence_trail(evidence)
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert set(REQUIRED_EVIDENCE_FIELDS) <= set(evidence["required_fields"])
        decisions = {record["decision"] for record in evidence["example_records"]}
        assert {"approved", "blocked", "revisions_required"} <= decisions
        for record in evidence["example_records"]:
            assert "not_platform_upload" in record["approval_scope"]
        assert any("Do not store secrets" in rule for rule in evidence["privacy_rules"])
        assert evidence["publish_allowed"] is False


def test_evidence_trail_catches_missing_fields_and_platform_scope_regression() -> None:
    evidence = build_evidence_trail()
    evidence["required_fields"].remove("reviewer")
    evidence["example_records"][0]["approval_scope"] = "platform_upload_allowed"

    result = validate_evidence_trail(evidence)

    assert result["is_valid"] is False
    assert "evidence fields missing" in result["errors"]
    assert "approval scope must not be platform upload" in result["errors"]


def test_p29_closeout_checklist_and_example_are_valid() -> None:
    generated = build_p29_closeout_checklist()
    example = _read_json(EXAMPLES["closeout"])

    for checklist in (generated, example):
        result = validate_p29_closeout(checklist)
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert [task["issue"] for task in checklist["child_tasks"]] == [362, 363, 364, 365, 366, 367]
        assert checklist["no_auto_publish_path"] is True
        assert checklist["no_platform_upload"] is True
        assert checklist["human_review_required"] is True
        assert checklist["publish_allowed"] is False
        assert checklist["review_required"] is True


def test_p29_closeout_references_all_artifacts_and_guardrails() -> None:
    checklist = _read_json(EXAMPLES["closeout"])
    all_artifacts = {artifact for task in checklist["child_tasks"] for artifact in task["artifacts"]}

    for required in [
        "src/editorial_status.py",
        "src/p29_governance.py",
        "docs/operations/p29-step-02.md",
        "docs/operations/p29-step-03.md",
        "docs/operations/p29-step-04.md",
        "docs/operations/p29-step-05.md",
        "docs/operations/p29-closeout-report.md",
        "docs/operations/p29-closeout-checklist.json",
        "tests/integration/test_p29_batch_02_06.py",
    ]:
        assert required in all_artifacts
        assert Path(required).exists(), required

    for guardrail in [
        "No automated approval.",
        "No legal clearance.",
        "No direct platform publishing.",
        "No direct platform upload.",
        "No secrets or credential storage.",
        "No customer data storage.",
        "No bypass of P26 risk rules.",
        "No bypass of P29 human/editorial approval.",
        "No publish permission from preview renders.",
        "No platform upload permission from export manifests.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]


def test_p29_batch_contract_outputs_are_deterministic() -> None:
    assert build_human_review_checklist() == build_human_review_checklist()
    assert build_publish_readiness_manifests() == build_publish_readiness_manifests()
    assert build_render_rules() == build_render_rules()
    assert build_evidence_trail() == build_evidence_trail()
    assert build_p29_closeout_checklist() == build_p29_closeout_checklist()
