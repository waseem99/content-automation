"""P50 local creative QA and pilot scoring engine.

This module scores P49 pilot batches before production, rendering, UI/API, or
cloud deployment. It creates baseline scorecards, human review fields, batch
summary, and local review files.

It does not replace human creative review and does not deploy, render, download,
upload, publish, call external services, or guarantee performance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

P50_QA_VERSION = "p50.creative_qa_pack.v1"
QA_SCORECARDS_FILENAME = "qa_scorecards.json"
QA_SUMMARY_FILENAME = "qa_summary.md"
QA_SCORECARD_DIRNAME = "qa_scorecards"

DIMENSION_WEIGHTS = {
    "hook_strength": 0.16,
    "clarity": 0.14,
    "retention_potential": 0.16,
    "platform_fit": 0.12,
    "originality": 0.12,
    "rights_readiness": 0.12,
    "monetization_fit": 0.10,
    "production_feasibility": 0.08,
}

RUBRIC = {
    "hook_strength": "First 3 seconds create curiosity, specificity, or useful tension.",
    "clarity": "Viewer can understand the promise, steps, and payoff without extra context.",
    "retention_potential": "Script/structure has pacing, beat changes, and a clear payoff.",
    "platform_fit": "Format, pacing, CTA, and caption style match the target platform.",
    "originality": "Idea feels transformed, specific, and not dependent on copied IP/trends.",
    "rights_readiness": "Assets, likeness, music, references, and sources are safe for review.",
    "monetization_fit": "CTA and route fit the audience without hard selling or policy risk.",
    "production_feasibility": "Producer/editor can make it with practical, available assets.",
}


def load_pilot_index(path: str | Path) -> dict[str, Any]:
    """Load a local pilot_index.json file."""

    index_path = Path(path)
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"pilots": data, "output_root": str(index_path.parent)}
    if not isinstance(data, dict) or not isinstance(data.get("pilots"), list):
        raise ValueError("Pilot index must be an object with a pilots list or a list of pilot objects.")
    data.setdefault("output_root", str(index_path.parent))
    return data


def normalize_qa_input(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Normalize P49 batch result or pilot_index path into pilot records."""

    if isinstance(source, (str, Path)):
        source = load_pilot_index(source)
    pilots = source.get("pilots", []) if isinstance(source, dict) else []
    if not pilots:
        return {"is_valid": False, "validation_errors": ["missing_pilots"]}
    normalized = []
    for index, pilot in enumerate(pilots, start=1):
        normalized.append({
            "pilot_number": int(pilot.get("pilot_number") or index),
            "pilot_name": str(pilot.get("pilot_name") or f"pilot-{index}"),
            "topic": str(pilot.get("topic") or "unknown topic"),
            "platform": str(pilot.get("platform") or "unknown"),
            "output_dir": str(pilot.get("output_dir") or ""),
            "is_valid": bool(pilot.get("is_valid", True)),
            "pipeline_status": str(pilot.get("pipeline_status") or "revise"),
            "rights_gate": str(pilot.get("rights_gate") or "revise"),
            "engagement_score": _safe_int(pilot.get("engagement_score"), 70),
            "monetization_status": str(pilot.get("monetization_status") or "needs_packaging_improvement"),
            "production_ready": bool(pilot.get("production_ready", False)),
            "template_platforms": list(pilot.get("template_platforms") or []),
            "platform_templates_path": str(pilot.get("platform_templates_path") or ""),
        })
    return {
        "is_valid": True,
        "pilots": normalized,
        "output_root": str(source.get("output_root") or source.get("batch_root") or ""),
    }


def build_creative_qa_pack(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Build creative QA scorecards and batch summary."""

    normalized = normalize_qa_input(source)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P50_QA_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }
    scorecards = [score_pilot(pilot) for pilot in normalized["pilots"]]
    summary = build_batch_qa_summary(scorecards)
    return {
        "schema_version": P50_QA_VERSION,
        "is_valid": True,
        "pilot_count": len(scorecards),
        "scorecards": scorecards,
        "batch_summary": summary,
        "rubric": RUBRIC,
        "human_review_required": True,
        "human_review_fields": human_review_fields(),
        **_guardrails(),
    }


def score_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    """Generate baseline QA scorecard for one pilot."""

    engagement = _safe_int(pilot.get("engagement_score"), 70)
    rights_gate = pilot.get("rights_gate", "revise")
    monetization_status = pilot.get("monetization_status", "needs_packaging_improvement")
    production_ready = bool(pilot.get("production_ready"))
    platform_count = len(pilot.get("template_platforms") or [])
    scores = {
        "hook_strength": _clamp(engagement + 2),
        "clarity": _clamp(engagement),
        "retention_potential": _clamp(engagement - 2),
        "platform_fit": 90 if platform_count >= 5 else 80 if platform_count >= 3 else 68,
        "originality": 84 if rights_gate == "pass" else 72 if rights_gate == "revise" else 45,
        "rights_readiness": 94 if rights_gate == "pass" else 70 if rights_gate == "revise" else 35,
        "monetization_fit": _monetization_score(monetization_status),
        "production_feasibility": 90 if production_ready else 64,
    }
    overall = weighted_score(scores)
    recommendation = recommend_pilot(scores, overall, pilot)
    return {
        "pilot_number": pilot["pilot_number"],
        "pilot_name": pilot["pilot_name"],
        "topic": pilot["topic"],
        "platform": pilot["platform"],
        "output_dir": pilot["output_dir"],
        "baseline_scores": scores,
        "weighted_overall_score": overall,
        "recommendation": recommendation,
        "top_issues": top_issues(scores, pilot),
        "next_actions": next_actions(scores, recommendation),
        "human_review": human_review_fields(),
        "human_review_required_before_production": True,
        "performance_guaranteed": False,
    }


def weighted_score(scores: dict[str, int]) -> int:
    return int(round(sum(scores[key] * weight for key, weight in DIMENSION_WEIGHTS.items())))


def recommend_pilot(scores: dict[str, int], overall: int, pilot: dict[str, Any]) -> str:
    if not pilot.get("is_valid") or scores["rights_readiness"] < 55 or scores["production_feasibility"] < 60:
        return "block"
    if overall >= 82 and scores["rights_readiness"] >= 85 and scores["platform_fit"] >= 80:
        return "accept_for_human_review"
    return "revise_before_production"


def build_batch_qa_summary(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = sum(1 for item in scorecards if item["recommendation"] == "accept_for_human_review")
    revise = sum(1 for item in scorecards if item["recommendation"] == "revise_before_production")
    blocked = sum(1 for item in scorecards if item["recommendation"] == "block")
    avg_score = int(round(sum(item["weighted_overall_score"] for item in scorecards) / max(len(scorecards), 1)))
    if blocked:
        decision = "block"
    elif avg_score >= 82 and accepted >= max(1, len(scorecards) - 1):
        decision = "accept_for_manual_production_review"
    else:
        decision = "revise_pilots_before_production"
    return {
        "pilot_count": len(scorecards),
        "average_score": avg_score,
        "accepted_count": accepted,
        "revise_count": revise,
        "blocked_count": blocked,
        "batch_decision": decision,
        "top_batch_issues": batch_issues(scorecards),
        "next_actions": batch_next_actions(decision),
        "human_review_required": True,
    }


def write_creative_qa_files(source: dict[str, Any] | str | Path, output_root: str | Path | None = None) -> dict[str, Any]:
    """Write QA scorecards and summary files locally."""

    qa_pack = build_creative_qa_pack(source)
    if not qa_pack.get("is_valid"):
        return qa_pack
    root = _resolve_output_root(source, output_root)
    root.mkdir(parents=True, exist_ok=True)
    scorecard_dir = root / QA_SCORECARD_DIRNAME
    scorecard_dir.mkdir(exist_ok=True)
    for scorecard in qa_pack["scorecards"]:
        filename = f"{slugify(scorecard['pilot_name'])}.md"
        (scorecard_dir / filename).write_text(render_scorecard_markdown(scorecard), encoding="utf-8")
    scorecards_path = root / QA_SCORECARDS_FILENAME
    summary_path = root / QA_SUMMARY_FILENAME
    scorecards_path.write_text(_json_dump(qa_pack), encoding="utf-8")
    summary_path.write_text(render_batch_summary_markdown(qa_pack), encoding="utf-8")
    return {
        **qa_pack,
        "output_root": str(root),
        "qa_scorecards_path": str(scorecards_path),
        "qa_summary_path": str(summary_path),
        "qa_scorecard_dir": str(scorecard_dir),
    }


def render_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {name} | {score} | {RUBRIC[name]} |" for name, score in scorecard["baseline_scores"].items()
    )
    actions = "\n".join(f"- {item}" for item in scorecard["next_actions"])
    issues = "\n".join(f"- {item}" for item in scorecard["top_issues"])
    return f"""# Creative QA Scorecard — {scorecard['pilot_name']}

## Pilot
- Topic: {scorecard['topic']}
- Platform: {scorecard['platform']}
- Recommendation: {scorecard['recommendation']}
- Baseline score: {scorecard['weighted_overall_score']}

## Baseline Scores

| Dimension | Score | Rubric |
|---|---:|---|
{rows}

## Top Issues
{issues or '- None'}

## Next Actions
{actions or '- Run final human review.'}

## Human Review
- Reviewer name:
- Final human score:
- Approval status: approve / revise / block
- Revision notes:
- Production decision:

Human review is required before production or publishing.
"""


def render_batch_summary_markdown(qa_pack: dict[str, Any]) -> str:
    summary = qa_pack["batch_summary"]
    rows = "\n".join(
        f"| {item['pilot_name']} | {item['platform']} | {item['weighted_overall_score']} | {item['recommendation']} |"
        for item in qa_pack["scorecards"]
    )
    actions = "\n".join(f"- {item}" for item in summary["next_actions"])
    return f"""# Batch Creative QA Summary

- Batch decision: {summary['batch_decision']}
- Average score: {summary['average_score']}
- Accepted: {summary['accepted_count']}
- Revise: {summary['revise_count']}
- Blocked: {summary['blocked_count']}

| Pilot | Platform | Score | Recommendation |
|---|---|---:|---|
{rows}

## Next Actions
{actions}

No deployment, rendering, uploading, publishing, or performance guarantee was performed. Human review is required.
"""


def human_review_fields() -> dict[str, Any]:
    return {
        "reviewer_name": "",
        "final_human_score": None,
        "approval_status": "pending",
        "revision_notes": "",
        "production_decision": "pending",
    }


def top_issues(scores: dict[str, int], pilot: dict[str, Any]) -> list[str]:
    issues = [f"{name} below 75" for name, score in scores.items() if score < 75]
    if not pilot.get("production_ready"):
        issues.append("Production folder is not marked ready.")
    return issues[:5]


def next_actions(scores: dict[str, int], recommendation: str) -> list[str]:
    if recommendation == "block":
        return ["Resolve blockers before production.", "Run rights and source review again."]
    actions = [f"Improve {name.replace('_', ' ')}." for name, score in scores.items() if score < 80]
    actions.append("Complete human creative review before production.")
    return actions[:6]


def batch_issues(scorecards: list[dict[str, Any]]) -> list[str]:
    issue_counts: dict[str, int] = {}
    for card in scorecards:
        for issue in card["top_issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    return [item for item, _count in sorted(issue_counts.items(), key=lambda pair: pair[1], reverse=True)[:5]]


def batch_next_actions(decision: str) -> list[str]:
    if decision == "block":
        return ["Fix blocked pilots before any production work.", "Re-run local QA after revisions."]
    if decision == "accept_for_manual_production_review":
        return ["Assign human reviewer.", "Approve or revise each pilot manually.", "Only then move selected pilots to production."]
    return ["Revise low-scoring pilots.", "Re-run local QA.", "Do not start deployment/UI work yet."]


def _resolve_output_root(source: dict[str, Any] | str | Path, output_root: str | Path | None) -> Path:
    if output_root is not None:
        return Path(output_root).expanduser().resolve()
    if isinstance(source, (str, Path)):
        return Path(source).expanduser().resolve().parent
    if source.get("output_root"):
        return Path(source["output_root"]).expanduser().resolve()
    return Path("outputs/qa").resolve()


def _monetization_score(status: str) -> int:
    if status == "ready_for_human_review":
        return 88
    if status == "not_ready":
        return 45
    return 72


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "pilot"


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "api_server_started": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "performance_guaranteed": False,
        "human_review_required_before_production": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local creative QA scorecards for a pilot batch.")
    parser.add_argument("pilot_index_json", help="Path to local pilot_index.json file.")
    parser.add_argument("--output-root", default=None, help="Optional output root for QA files.")
    args = parser.parse_args(argv)
    try:
        result = write_creative_qa_files(args.pilot_index_json, args.output_root)
        print(_json_dump({"ok": result.get("is_valid", False), "qa_summary_path": result.get("qa_summary_path")}), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
