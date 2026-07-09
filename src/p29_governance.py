"""P29 editorial governance helper contracts.

This module covers the remaining P29 contracts after the editorial status model:
human review checklist, publish-readiness manifest, render-mode rules, evidence
trail requirements, and closeout validation. It does not implement UI,
authentication, legal clearance, platform upload, publishing, or storage of
secrets/customer data.
"""

from __future__ import annotations

from typing import Any

CHECKLIST_SCHEMA_VERSION = "p29.human_review_checklist.v1"
MANIFEST_SCHEMA_VERSION = "p29.publish_readiness_manifest.v1"
RENDER_RULES_SCHEMA_VERSION = "p29.preview_publish_render_rules.v1"
EVIDENCE_SCHEMA_VERSION = "p29.editorial_evidence_trail.v1"
CLOSEOUT_SCHEMA_VERSION = "p29.closeout_checklist.v1"

REVIEW_STATES = ("pass", "fail", "needs_revision")
REQUIRED_CHECKLIST_SECTIONS = (
    "script_accuracy",
    "hook_strength",
    "title_thumbnail_alignment",
    "asset_rights",
    "image_attribution",
    "music_license",
    "captions",
    "factual_sources",
    "originality",
    "platform_fit",
)
REVIEW_VARIANTS = ("shorts", "explainer")
PUBLISH_READINESS_STATES = ("not_publish_ready", "review_required", "publish_export_ready")
MANIFEST_FIELDS = (
    "content_package_path",
    "risk_report_path",
    "export_paths",
    "editorial_status",
    "approval_owner",
    "approval_timestamp",
    "blockers",
    "next_actions",
)
RENDER_MODES = ("preview", "publish")
REQUIRED_EVIDENCE_FIELDS = (
    "reviewer",
    "decision",
    "timestamp",
    "reviewed_package_version",
    "blockers",
    "required_changes",
    "source_risk_notes",
    "approval_scope",
)
EVIDENCE_DECISIONS = ("approved", "blocked", "revisions_required")


def build_human_review_checklist() -> dict[str, Any]:
    sections = [
        {
            "section": section,
            "states": list(REVIEW_STATES),
            "operator_prompt": f"Review {section.replace('_', ' ')} and mark pass, fail, or needs_revision.",
            "required_before_approval": True,
        }
        for section in REQUIRED_CHECKLIST_SECTIONS
    ]
    return {
        "schema_version": CHECKLIST_SCHEMA_VERSION,
        "parent_epic": 331,
        "issue": 363,
        "content_type": "human_review_checklist",
        "states": list(REVIEW_STATES),
        "sections": sections,
        "variants": {
            "shorts": {
                "format": "vertical_short_form",
                "extra_checks": ["first_two_seconds_hook", "safe_caption_burn_in", "mobile_readability"],
            },
            "explainer": {
                "format": "explainers_and_long_form",
                "extra_checks": ["chapter_logic", "source_density", "claim_context"],
            },
        },
        "operator_notes": [
            "Use simple pass, fail, or needs_revision decisions.",
            "Any fail blocks approval.",
            "Any needs_revision returns the package to revisions_required.",
            "This checklist does not provide legal clearance.",
        ],
        "publish_allowed": False,
        "review_required": True,
    }


def build_publish_readiness_manifests() -> dict[str, Any]:
    base = {
        "content_package_path": "content_package.json",
        "risk_report_path": "monetization_risk_report.json",
        "export_paths": ["exports/youtube_shorts/package.json", "exports/youtube_long_form/package.json"],
    }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "parent_epic": 331,
        "issue": 364,
        "content_type": "publish_readiness_manifest_examples",
        "allowed_readiness_states": list(PUBLISH_READINESS_STATES),
        "required_fields": list(MANIFEST_FIELDS),
        "examples": [
            {
                **base,
                "manifest_id": "manifest-blocked-example",
                "readiness_state": "not_publish_ready",
                "editorial_status": "revisions_required",
                "approval_owner": None,
                "approval_timestamp": None,
                "blockers": ["rights_review_required", "missing_source_attribution"],
                "next_actions": ["replace unlicensed asset", "complete source attribution"],
                "platform_export_is_upload": False,
            },
            {
                **base,
                "manifest_id": "manifest-review-required-example",
                "readiness_state": "review_required",
                "editorial_status": "editorial_review",
                "approval_owner": "human_reviewer_required",
                "approval_timestamp": None,
                "blockers": [],
                "next_actions": ["complete human checklist", "confirm P26 risk clearance"],
                "platform_export_is_upload": False,
            },
            {
                **base,
                "manifest_id": "manifest-approved-example",
                "readiness_state": "publish_export_ready",
                "editorial_status": "publish_export_ready",
                "approval_owner": "reviewer_001",
                "approval_timestamp": "2026-07-09T00:00:00Z",
                "blockers": [],
                "next_actions": ["manual export handoff", "record external publish only after human action"],
                "platform_export_is_upload": False,
            },
        ],
        "alignment": {
            "p24_package_required": True,
            "p25_packaging_quality_required": True,
            "p26_risk_clearance_required": True,
            "p27_exports_are_not_uploads": True,
            "p29_human_approval_required": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def build_render_rules() -> dict[str, Any]:
    return {
        "schema_version": RENDER_RULES_SCHEMA_VERSION,
        "parent_epic": 331,
        "issue": 365,
        "content_type": "preview_publish_render_rules",
        "render_modes": {
            "preview": {
                "output_name": "preview_video.mp4",
                "allowed_when": ["draft", "package_generated", "editorial_review", "rights_review", "revisions_required", "approved"],
                "purpose": "Internal review only; not a publishing asset.",
                "publish_ready": False,
            },
            "publish": {
                "output_name": "publish_video.mp4",
                "allowed_when": ["publish_export_ready"],
                "requires": ["approved package", "P26 risk clear", "P29 editorial approval", "rights review clear"],
                "purpose": "Manual export-ready asset after gates pass; still not a platform upload.",
                "publish_ready": True,
            },
        },
        "readme_mismatch": {
            "observed_terms": ["final_video.mp4", "preview_video.mp4", "publish_video.mp4"],
            "recommended_correction": "Use preview_video.mp4 for review renders and publish_video.mp4 only after publish_export_ready; avoid treating final_video.mp4 as approval.",
            "final_video_mp4_is_ambiguous": True,
        },
        "blocked_rules": [
            "publish render is blocked without publish_export_ready",
            "preview render is not upload permission",
            "publish render is not direct platform publishing",
        ],
        "publish_allowed": False,
        "review_required": True,
    }


def build_evidence_trail() -> dict[str, Any]:
    def record(decision: str, blockers: list[str], required_changes: list[str]) -> dict[str, Any]:
        return {
            "reviewer": "reviewer_001",
            "decision": decision,
            "timestamp": "2026-07-09T00:00:00Z",
            "reviewed_package_version": "content_package.json@v1",
            "blockers": blockers,
            "required_changes": required_changes,
            "source_risk_notes": "Internal evidence only; no secrets, customer data, or external account details.",
            "approval_scope": "package_export_readiness_only_not_platform_upload",
            "publish_readiness_manifest_path": "docs/operations/p29-publish-readiness-manifest-example.json",
        }

    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "parent_epic": 331,
        "issue": 366,
        "content_type": "editorial_evidence_trail_requirements",
        "required_fields": list(REQUIRED_EVIDENCE_FIELDS),
        "privacy_rules": [
            "Do not store secrets.",
            "Do not store customer data.",
            "Do not store unnecessary external account details.",
            "Evidence is internal and not a platform upload artifact.",
        ],
        "example_records": [
            record("approved", [], []),
            record("blocked", ["p26_publish_block", "rights_review_required"], ["clear risk blocker", "replace asset"]),
            record("revisions_required", ["editorial_changes_required"], ["tighten hook", "add source context"]),
        ],
        "publish_allowed": False,
        "review_required": True,
    }


def build_p29_closeout_checklist() -> dict[str, Any]:
    return {
        "schema_version": CLOSEOUT_SCHEMA_VERSION,
        "parent_epic": 331,
        "closeout_issue": 367,
        "child_tasks": [
            {"issue": 362, "status": "complete", "artifacts": ["src/editorial_status.py", "docs/operations/p29-step-01.md", "tests/integration/test_p29_step_01.py"]},
            {"issue": 363, "status": "complete_after_merge", "artifacts": ["src/p29_governance.py", "docs/operations/p29-step-02.md", "docs/operations/p29-human-review-checklist-example.json"]},
            {"issue": 364, "status": "complete_after_merge", "artifacts": ["src/p29_governance.py", "docs/operations/p29-step-03.md", "docs/operations/p29-publish-readiness-manifest-example.json"]},
            {"issue": 365, "status": "complete_after_merge", "artifacts": ["src/p29_governance.py", "docs/operations/p29-step-04.md", "docs/operations/p29-render-rules-example.json"]},
            {"issue": 366, "status": "complete_after_merge", "artifacts": ["src/p29_governance.py", "docs/operations/p29-step-05.md", "docs/operations/p29-editorial-evidence-example.json"]},
            {"issue": 367, "status": "complete_after_merge", "artifacts": ["docs/operations/p29-closeout-report.md", "docs/operations/p29-closeout-checklist.json", "tests/integration/test_p29_batch_02_06.py"]},
        ],
        "no_auto_publish_path": True,
        "no_platform_upload": True,
        "human_review_required": True,
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_human_review_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(checklist.get("schema_version") == CHECKLIST_SCHEMA_VERSION, errors, "checklist schema mismatch")
    sections = [s.get("section") for s in checklist.get("sections", []) if isinstance(s, dict)]
    _require(set(REQUIRED_CHECKLIST_SECTIONS) <= set(sections), errors, "required checklist sections missing")
    _require(set(REVIEW_VARIANTS) <= set(checklist.get("variants", {})), errors, "review variants missing")
    _require(tuple(checklist.get("states", [])) == REVIEW_STATES, errors, "review states mismatch")
    _require(checklist.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(checklist.get("review_required") is True, errors, "review_required must remain true")
    return {"is_valid": not errors, "errors": errors}


def validate_publish_readiness_manifests(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION, errors, "manifest schema mismatch")
    _require(set(MANIFEST_FIELDS) <= set(manifest.get("required_fields", [])), errors, "manifest fields missing")
    examples = manifest.get("examples", [])
    states = [example.get("readiness_state") for example in examples if isinstance(example, dict)]
    _require(set(PUBLISH_READINESS_STATES) <= set(states), errors, "readiness states missing")
    for example in examples:
        if isinstance(example, dict):
            _require(set(MANIFEST_FIELDS) <= set(example), errors, "manifest example missing fields")
            _require(example.get("platform_export_is_upload") is False, errors, "platform export must not be upload")
    _require(manifest.get("alignment", {}).get("p27_exports_are_not_uploads") is True, errors, "P27 export upload distinction required")
    _require(manifest.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    return {"is_valid": not errors, "errors": errors}


def validate_render_rules(rules: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(rules.get("schema_version") == RENDER_RULES_SCHEMA_VERSION, errors, "render rules schema mismatch")
    render_modes = rules.get("render_modes", {})
    _require(set(RENDER_MODES) <= set(render_modes), errors, "preview/publish render modes missing")
    _require(render_modes.get("preview", {}).get("output_name") == "preview_video.mp4", errors, "preview_video.mp4 required")
    _require(render_modes.get("publish", {}).get("output_name") == "publish_video.mp4", errors, "publish_video.mp4 required")
    _require(rules.get("readme_mismatch", {}).get("final_video_mp4_is_ambiguous") is True, errors, "final_video.mp4 mismatch must be recorded")
    _require(rules.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    return {"is_valid": not errors, "errors": errors}


def validate_evidence_trail(evidence: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(evidence.get("schema_version") == EVIDENCE_SCHEMA_VERSION, errors, "evidence schema mismatch")
    _require(set(REQUIRED_EVIDENCE_FIELDS) <= set(evidence.get("required_fields", [])), errors, "evidence fields missing")
    decisions = [record.get("decision") for record in evidence.get("example_records", []) if isinstance(record, dict)]
    _require(set(EVIDENCE_DECISIONS) <= set(decisions), errors, "required evidence decisions missing")
    for record in evidence.get("example_records", []):
        if isinstance(record, dict):
            _require(set(REQUIRED_EVIDENCE_FIELDS) <= set(record), errors, "evidence record missing fields")
            _require("not_platform_upload" in record.get("approval_scope", ""), errors, "approval scope must not be platform upload")
    _require(any("Do not store secrets" in rule for rule in evidence.get("privacy_rules", [])), errors, "secret privacy rule required")
    _require(evidence.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    return {"is_valid": not errors, "errors": errors}


def validate_p29_closeout(checklist: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    _require(checklist.get("schema_version") == CLOSEOUT_SCHEMA_VERSION, errors, "closeout schema mismatch")
    _require([task.get("issue") for task in checklist.get("child_tasks", [])] == [362, 363, 364, 365, 366, 367], errors, "P29 child task list mismatch")
    _require(checklist.get("no_auto_publish_path") is True, errors, "no auto-publish path must be confirmed")
    _require(checklist.get("no_platform_upload") is True, errors, "no platform upload must be confirmed")
    _require(checklist.get("human_review_required") is True, errors, "human review requirement must be confirmed")
    _require(checklist.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    return {"is_valid": not errors, "errors": errors}
