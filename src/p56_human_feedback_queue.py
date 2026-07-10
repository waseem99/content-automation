"""P56 local human feedback and revision queue.

This module converts reviewer decisions from the P55 demo gallery into local
feedback artifacts: a normalized feedback summary, approved candidate list,
rejected list, and prioritized revision queue.

It does not deploy, host a UI/API, render video, download assets, upload,
publish, call external services, or automate final production approval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

P56_FEEDBACK_VERSION = "p56.local_human_feedback_queue.v1"
SUMMARY_FILENAME = "review_feedback_summary.json"
REVISION_QUEUE_FILENAME = "revision_queue.json"
REPORT_FILENAME = "review_feedback_report.md"
DECISIONS = {"approve_for_production", "revise", "reject"}


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object.")
    return data


def normalize_feedback_input(
    gallery: dict[str, Any] | str | Path,
    feedback: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Normalize P55 gallery and reviewer feedback sources."""

    try:
        gallery_data = load_json(gallery) if isinstance(gallery, (str, Path)) else gallery
        feedback_data = load_json(feedback) if isinstance(feedback, (str, Path)) else feedback
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"is_valid": False, "validation_errors": [str(exc)]}
    if not isinstance(gallery_data, dict) or not isinstance(gallery_data.get("demos"), list):
        return {"is_valid": False, "validation_errors": ["missing_gallery_demos"]}
    if not isinstance(feedback_data, dict):
        return {"is_valid": False, "validation_errors": ["feedback_must_be_object"]}
    reviews = feedback_data.get("reviews") or feedback_data.get("feedback") or []
    if not isinstance(reviews, list):
        return {"is_valid": False, "validation_errors": ["feedback_reviews_must_be_list"]}
    return {
        "is_valid": True,
        "gallery": gallery_data,
        "reviews": [item for item in reviews if isinstance(item, dict)],
        "reviewer_name": str(feedback_data.get("reviewer_name") or ""),
        "review_round": str(feedback_data.get("review_round") or "manual_review"),
    }


def build_human_feedback_queue(
    gallery: dict[str, Any] | str | Path,
    feedback: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Build normalized feedback summary and revision queue."""

    normalized = normalize_feedback_input(gallery, feedback)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P56_FEEDBACK_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }

    demos = normalized["gallery"].get("demos", [])
    feedback_by_slug = {
        str(item.get("demo_slug") or item.get("demo_id") or item.get("slug")): item
        for item in normalized["reviews"]
    }
    normalized_reviews = [normalize_demo_review(demo, feedback_by_slug.get(str(demo.get("demo_slug")))) for demo in demos]
    summary = summarize_reviews(normalized_reviews)
    revision_queue = build_revision_queue(normalized_reviews)
    approved = [candidate_view(item) for item in normalized_reviews if item["decision"] == "approve_for_production"]
    rejected = [candidate_view(item) for item in normalized_reviews if item["decision"] == "reject"]

    return {
        "schema_version": P56_FEEDBACK_VERSION,
        "is_valid": True,
        "review_round": normalized["review_round"],
        "reviewer_name": normalized["reviewer_name"],
        "summary": summary,
        "normalized_reviews": normalized_reviews,
        "approved_candidates": approved,
        "rejected_demos": rejected,
        "revision_queue": revision_queue,
        "human_approval_required_before_production": True,
        **_guardrails(),
    }


def normalize_demo_review(demo: dict[str, Any], feedback: dict[str, Any] | None) -> dict[str, Any]:
    feedback = feedback or {}
    decision = normalize_decision(feedback.get("decision"), missing=not bool(feedback))
    score = normalize_score(feedback.get("score"), default=50 if decision == "revise" else 0)
    strengths = as_list(feedback.get("strengths"))
    issues = as_list(feedback.get("issues"))
    requested_changes = as_list(feedback.get("requested_changes"))
    approval_notes = str(feedback.get("approval_notes") or feedback.get("notes") or "")
    signals = demo.get("signals", {}) if isinstance(demo.get("signals"), dict) else {}
    return {
        "demo_slug": str(demo.get("demo_slug") or demo.get("demo_id") or "demo"),
        "topic": demo.get("topic"),
        "platform": demo.get("platform"),
        "audience": demo.get("audience"),
        "workspace_index_href": demo.get("workspace_index_href"),
        "workspace_index_path": demo.get("workspace_index_path"),
        "decision": decision,
        "score": score,
        "missing_feedback": not bool(feedback),
        "strengths": strengths,
        "issues": issues,
        "requested_changes": requested_changes,
        "approval_notes": approval_notes,
        "signals": {
            "pipeline_status": signals.get("pipeline_status") or demo.get("pipeline_status"),
            "rights_gate": signals.get("rights_gate") or demo.get("rights_gate"),
            "engagement_score": signals.get("engagement_score") or demo.get("engagement_score"),
            "monetization_status": signals.get("monetization_status") or demo.get("monetization_status"),
            "production_ready": signals.get("production_ready") or demo.get("production_ready"),
        },
    }


def normalize_decision(value: Any, *, missing: bool = False) -> str:
    decision = str(value or "").strip().lower()
    if missing:
        return "revise"
    if decision in DECISIONS:
        return decision
    if decision in {"approve", "approved", "produce", "production"}:
        return "approve_for_production"
    if decision in {"reject", "rejected", "drop"}:
        return "reject"
    return "revise"


def normalize_score(value: Any, *, default: int = 50) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))


def summarize_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"approve_for_production": 0, "revise": 0, "reject": 0}
    missing = 0
    scores = []
    for review in reviews:
        counts[review["decision"]] = counts.get(review["decision"], 0) + 1
        missing += 1 if review.get("missing_feedback") else 0
        scores.append(int(review.get("score", 0)))
    return {
        "reviewed_demo_count": len(reviews),
        "approved_count": counts["approve_for_production"],
        "revise_count": counts["revise"],
        "rejected_count": counts["reject"],
        "missing_feedback_count": missing,
        "average_score": int(sum(scores) / len(scores)) if scores else 0,
        "decision_counts": counts,
    }


def build_revision_queue(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = []
    for review in reviews:
        if review["decision"] == "approve_for_production":
            continue
        priority_score = revision_priority_score(review)
        queue.append({
            "demo_slug": review["demo_slug"],
            "topic": review.get("topic"),
            "platform": review.get("platform"),
            "decision": review["decision"],
            "review_score": review["score"],
            "priority": priority_label(priority_score),
            "priority_score": priority_score,
            "issue_summary": review.get("issues", []),
            "requested_changes": review.get("requested_changes", []),
            "workspace_index_path": review.get("workspace_index_path"),
            "revision_instruction": revision_instruction(review),
            "human_review_required_after_revision": True,
        })
    return sorted(queue, key=lambda item: item["priority_score"], reverse=True)


def revision_priority_score(review: dict[str, Any]) -> int:
    score_gap = max(0, 100 - int(review.get("score", 0)))
    issue_weight = len(review.get("issues", [])) * 8
    change_weight = len(review.get("requested_changes", [])) * 10
    reject_weight = 25 if review.get("decision") == "reject" else 0
    missing_weight = 15 if review.get("missing_feedback") else 0
    return score_gap + issue_weight + change_weight + reject_weight + missing_weight


def priority_label(score: int) -> str:
    if score >= 90:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def revision_instruction(review: dict[str, Any]) -> str:
    changes = review.get("requested_changes") or review.get("issues") or []
    if changes:
        return "Revise around: " + "; ".join(str(item) for item in changes[:4])
    if review.get("missing_feedback"):
        return "Collect human review notes before regenerating this demo."
    return "Tighten hook, script specificity, storyboard usefulness, rights clarity, and monetization CTA."


def candidate_view(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "demo_slug": review["demo_slug"],
        "topic": review.get("topic"),
        "platform": review.get("platform"),
        "score": review.get("score"),
        "workspace_index_path": review.get("workspace_index_path"),
        "approval_notes": review.get("approval_notes", ""),
    }


def write_feedback_outputs(
    gallery: dict[str, Any] | str | Path,
    feedback: dict[str, Any] | str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    result = build_human_feedback_queue(gallery, feedback)
    if not result.get("is_valid"):
        return result
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / SUMMARY_FILENAME
    queue_path = root / REVISION_QUEUE_FILENAME
    report_path = root / REPORT_FILENAME
    summary_path.write_text(_json_dump(result), encoding="utf-8")
    queue_path.write_text(_json_dump({"schema_version": "p56.revision_queue.v1", "items": result["revision_queue"], **_guardrails()}), encoding="utf-8")
    report_path.write_text(render_feedback_report(result), encoding="utf-8")
    return {
        "schema_version": P56_FEEDBACK_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "review_feedback_summary_path": str(summary_path),
        "revision_queue_path": str(queue_path),
        "review_feedback_report_path": str(report_path),
        "approved_count": result["summary"]["approved_count"],
        "revision_queue_count": len(result["revision_queue"]),
        **_guardrails(),
    }


def render_feedback_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Review Feedback Report",
        "",
        f"Reviewer: {result.get('reviewer_name') or 'TBD'}",
        f"Review round: {result.get('review_round')}",
        "",
        "## Summary",
        f"- Approved: {summary['approved_count']}",
        f"- Revise: {summary['revise_count']}",
        f"- Rejected: {summary['rejected_count']}",
        f"- Missing feedback: {summary['missing_feedback_count']}",
        f"- Average score: {summary['average_score']}",
        "",
        "## Approved Candidates",
    ]
    approved = result.get("approved_candidates", [])
    lines.extend([f"- {item['demo_slug']} — {item.get('topic')} ({item.get('score')})" for item in approved] or ["- None yet."])
    lines.extend(["", "## Revision Queue"])
    queue = result.get("revision_queue", [])
    for item in queue:
        lines.extend([
            f"### {item['demo_slug']} — {item['priority'].upper()}",
            f"- Topic: {item.get('topic')}",
            f"- Platform: {item.get('platform')}",
            f"- Decision: {item.get('decision')}",
            f"- Score: {item.get('review_score')}",
            f"- Instruction: {item.get('revision_instruction')}",
            "",
        ])
    if not queue:
        lines.append("- No revision items.")
    lines.extend([
        "",
        "## Guardrails",
        "No deployment, hosted UI/API, rendering, upload, publishing, external calls, or automated final production approval was performed.",
    ])
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local human feedback reports and revision queue.")
    parser.add_argument("demo_gallery_json", help="Path to P55 demo_gallery.json.")
    parser.add_argument("review_feedback_json", help="Path to reviewer feedback JSON.")
    parser.add_argument("--output-root", default="outputs/demo-gallery", help="Local output root for feedback files.")
    args = parser.parse_args(argv)
    try:
        result = write_feedback_outputs(args.demo_gallery_json, args.review_feedback_json, args.output_root)
        print(_json_dump(_cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "output_root": result.get("output_root"),
        "approved_count": result.get("approved_count", 0),
        "revision_queue_count": result.get("revision_queue_count", 0),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


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
        "monetization_guaranteed": False,
        "performance_guaranteed": False,
        "human_review_required_before_production": True,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
