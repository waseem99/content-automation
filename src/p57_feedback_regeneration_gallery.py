"""P57 local feedback-driven regeneration gallery.

This module turns P56 human review feedback into revised demo briefs and then
uses the existing P55 local gallery builder to create a revised demo gallery.
It exists so reviewers can move from feedback to a second local review pass
without deployment, rendering, upload, publishing, external calls, or hosted UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.p55_creator_demo_gallery import build_creator_demo_gallery, load_demo_briefs

P57_REGEN_VERSION = "p57.feedback_regeneration_gallery.v1"
REVISED_BRIEFS_FILENAME = "revised_demo_briefs.json"
PATCH_SUMMARY_FILENAME = "feedback_patch_summary.json"
REPORT_FILENAME = "feedback_regeneration_report.md"
REVISED_GALLERY_DIR = "revised-gallery"


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object.")
    return data


def build_feedback_regeneration_gallery(
    original_briefs_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    feedback_source: dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    include_rejected: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build revised briefs and a revised local gallery from P56 feedback."""

    normalized = normalize_regeneration_input(original_briefs_source, feedback_source)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P57_REGEN_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }

    revised_briefs, patch_summary = build_revised_brief_library(
        normalized["original_briefs"],
        normalized["feedback"],
        include_rejected=include_rejected,
    )
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    revised_briefs_payload = {
        "schema_version": "p57.revised_demo_briefs.v1",
        "source_feedback_version": normalized["feedback"].get("schema_version"),
        "briefs": revised_briefs,
        "local_only": True,
        "human_review_required_before_production": True,
    }
    revised_briefs_path = root / REVISED_BRIEFS_FILENAME
    patch_summary_path = root / PATCH_SUMMARY_FILENAME
    report_path = root / REPORT_FILENAME
    revised_briefs_path.write_text(_json_dump(revised_briefs_payload), encoding="utf-8")
    patch_summary_path.write_text(_json_dump(patch_summary), encoding="utf-8")

    revised_gallery_root = root / REVISED_GALLERY_DIR
    revised_gallery = (
        build_creator_demo_gallery(revised_briefs_payload, revised_gallery_root, overwrite=overwrite)
        if revised_briefs
        else empty_revised_gallery(revised_gallery_root)
    )
    report_path.write_text(render_regeneration_report(patch_summary, revised_gallery), encoding="utf-8")

    return {
        "schema_version": P57_REGEN_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "revised_demo_briefs_path": str(revised_briefs_path),
        "feedback_patch_summary_path": str(patch_summary_path),
        "feedback_regeneration_report_path": str(report_path),
        "revised_gallery_root": str(revised_gallery_root),
        "revised_gallery": revised_gallery,
        "revised_demo_count": len(revised_briefs),
        "preserved_approved_count": len(patch_summary["preserved_approved_candidates"]),
        "skipped_count": len(patch_summary["skipped_items"]),
        "human_review_required_before_production": True,
        **_guardrails(),
    }


def normalize_regeneration_input(
    original_briefs_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    feedback_source: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Normalize original demo briefs and P56 feedback output."""

    try:
        original_briefs = load_demo_briefs(original_briefs_source)
        feedback = load_json(feedback_source) if isinstance(feedback_source, (str, Path)) else feedback_source
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"is_valid": False, "validation_errors": [str(exc)]}
    if not isinstance(feedback, dict):
        return {"is_valid": False, "validation_errors": ["feedback_must_be_object"]}
    if not isinstance(feedback.get("revision_queue"), list):
        return {"is_valid": False, "validation_errors": ["missing_revision_queue"]}
    return {
        "is_valid": True,
        "original_briefs": original_briefs,
        "feedback": feedback,
    }


def build_revised_brief_library(
    original_briefs: list[dict[str, Any]],
    feedback: dict[str, Any],
    *,
    include_rejected: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create revised demo briefs from P56 revision queue items."""

    original_by_slug = {brief_slug(item): item for item in original_briefs}
    original_by_id = {str(item.get("demo_id") or brief_slug(item)): item for item in original_briefs}
    revised_briefs: list[dict[str, Any]] = []
    applied_patches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for item in feedback.get("revision_queue", []):
        if not isinstance(item, dict):
            continue
        decision = str(item.get("decision") or "revise")
        if decision == "reject" and not include_rejected:
            skipped.append(skip_view(item, "rejected_item_excluded"))
            continue
        original = find_original_brief(item, original_by_slug, original_by_id)
        if not original:
            skipped.append(skip_view(item, "original_brief_not_found"))
            continue
        revised, patch = revise_brief(original, item)
        revised_briefs.append(revised)
        applied_patches.append(patch)

    patch_summary = {
        "schema_version": "p57.feedback_patch_summary.v1",
        "is_valid": True,
        "revised_demo_count": len(revised_briefs),
        "applied_patches": applied_patches,
        "preserved_approved_candidates": feedback.get("approved_candidates", []),
        "rejected_demos": feedback.get("rejected_demos", []),
        "skipped_items": skipped,
        "human_review_required_before_production": True,
        **_guardrails(),
    }
    return revised_briefs, patch_summary


def revise_brief(original: dict[str, Any], queue_item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply deterministic human-feedback notes to one brief."""

    original_slug = str(original.get("demo_id") or brief_slug(original))
    revised_slug = f"{original_slug}-revised"
    requested_changes = as_list(queue_item.get("requested_changes"))
    issues = as_list(queue_item.get("issues"))
    strengths = as_list(queue_item.get("strengths"))
    applied_changes = requested_changes or issues or ["Tighten creative execution based on reviewer feedback."]

    revised = dict(original)
    revised["demo_id"] = revised_slug
    revised["must_use_points"] = dedupe([
        *as_list(original.get("must_use_points")),
        *[f"Revision requirement: {item}" for item in applied_changes],
    ])
    revised["avoid"] = dedupe([
        *as_list(original.get("avoid")),
        *[f"Reviewer issue to avoid: {item}" for item in issues],
    ])
    revised["source_notes"] = dedupe([
        *as_list(original.get("source_notes")),
        f"Revised from human feedback on {original_slug}.",
        *[f"Reviewer requested change: {item}" for item in requested_changes],
    ])
    revised["tone"] = strengthen_tone(str(original.get("tone") or ""), queue_item)
    revised["revision_source"] = {
        "source_demo_slug": str(queue_item.get("demo_slug") or original_slug),
        "original_decision": str(queue_item.get("decision") or "revise"),
        "review_score": normalize_score(queue_item.get("score")),
        "priority": queue_item.get("priority"),
        "strengths_to_preserve": strengths,
        "issues_to_fix": issues,
        "requested_changes": requested_changes,
        "human_review_required_before_production": True,
    }

    patch = {
        "source_demo_slug": original_slug,
        "revised_demo_slug": revised_slug,
        "decision": str(queue_item.get("decision") or "revise"),
        "score": normalize_score(queue_item.get("score")),
        "priority": queue_item.get("priority"),
        "applied_changes": applied_changes,
        "issues_to_fix": issues,
        "strengths_to_preserve": strengths,
        "local_only": True,
    }
    return revised, patch


def find_original_brief(
    queue_item: dict[str, Any],
    original_by_slug: dict[str, dict[str, Any]],
    original_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        str(queue_item.get("demo_slug") or ""),
        str(queue_item.get("source_demo_slug") or ""),
        str(queue_item.get("demo_id") or ""),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        clean = candidate.removesuffix("-revised").removesuffix("-local")
        if candidate in original_by_slug:
            return original_by_slug[candidate]
        if candidate in original_by_id:
            return original_by_id[candidate]
        if clean in original_by_slug:
            return original_by_slug[clean]
        if clean in original_by_id:
            return original_by_id[clean]
    return None


def render_regeneration_report(patch_summary: dict[str, Any], revised_gallery: dict[str, Any]) -> str:
    """Render a local Markdown report for the regeneration pass."""

    lines = [
        "# Feedback-Driven Regeneration Report",
        "",
        f"Revised demo count: {patch_summary.get('revised_demo_count', 0)}",
        f"Preserved approved candidates: {len(patch_summary.get('preserved_approved_candidates', []))}",
        f"Skipped items: {len(patch_summary.get('skipped_items', []))}",
        f"Revised gallery valid: {bool(revised_gallery.get('is_valid'))}",
        f"Revised gallery index: {revised_gallery.get('gallery_index_path', 'not generated')}",
        "",
        "## Applied Patches",
        "",
    ]
    patches = patch_summary.get("applied_patches", [])
    if not patches:
        lines.append("No revised demos were generated.")
    for patch in patches:
        lines.extend([
            f"### {patch.get('source_demo_slug')} → {patch.get('revised_demo_slug')}",
            f"- Decision: {patch.get('decision')}",
            f"- Score: {patch.get('score')}",
            f"- Priority: {patch.get('priority')}",
            "- Applied changes:",
            *[f"  - {item}" for item in patch.get("applied_changes", [])],
            "",
        ])
    lines.extend([
        "## Guardrails",
        "",
        "- Local files only.",
        "- No deployment, upload, publishing, rendering, asset download, or external calls.",
        "- Human approval is still required before production.",
    ])
    return "\n".join(lines).strip() + "\n"


def write_feedback_regeneration_outputs(
    original_briefs_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    feedback_source: dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    include_rejected: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build and write a feedback-driven revised gallery."""

    return build_feedback_regeneration_gallery(
        original_briefs_source,
        feedback_source,
        output_root,
        include_rejected=include_rejected,
        overwrite=overwrite,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate revised demo gallery from human feedback.")
    parser.add_argument("original_briefs_json", help="Path to original P55 demo briefs JSON.")
    parser.add_argument("feedback_summary_json", help="Path to P56 review_feedback_summary.json.")
    parser.add_argument("--output-root", default="outputs/feedback-regeneration", help="Local output root.")
    parser.add_argument("--exclude-rejected", action="store_true", help="Skip rejected items instead of reworking them.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite generated revised gallery folders.")
    args = parser.parse_args(argv)
    try:
        result = write_feedback_regeneration_outputs(
            args.original_briefs_json,
            args.feedback_summary_json,
            args.output_root,
            include_rejected=not args.exclude_rejected,
            overwrite=args.overwrite,
        )
        print(_json_dump(cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


def empty_revised_gallery(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    return {
        "schema_version": "p55.local_creator_demo_gallery.v1",
        "is_valid": True,
        "output_root": str(root),
        "gallery_index_path": None,
        "demo_gallery_path": None,
        "demo_count": 0,
        "successful_demo_count": 0,
        "demos": [],
        **_guardrails(),
    }


def brief_slug(brief: dict[str, Any]) -> str:
    return str(brief.get("demo_id") or brief.get("topic") or "demo").strip().lower().replace(" ", "-")


def skip_view(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "demo_slug": item.get("demo_slug") or item.get("source_demo_slug") or item.get("demo_id"),
        "decision": item.get("decision"),
        "reason": reason,
        "local_only": True,
    }


def strengthen_tone(tone: str, queue_item: dict[str, Any]) -> str:
    extras = ["more specific", "editor-ready"]
    if str(queue_item.get("decision")) == "reject":
        extras.append("substantially reworked")
    combined = ", ".join([item for item in [tone, *extras] if item])
    return combined


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def dedupe(items: list[str]) -> list[str]:
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def normalize_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score))


def cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "output_root": result.get("output_root"),
        "revised_demo_count": result.get("revised_demo_count", 0),
        "revised_gallery_root": result.get("revised_gallery_root"),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "hosted_ui_created": False,
        "api_server_started": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "automated_final_approval": False,
        "creative_improvement_guaranteed": False,
        "monetization_guaranteed": False,
        "performance_guaranteed": False,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
