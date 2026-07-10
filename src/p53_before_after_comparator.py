"""P53 local before/after QA comparison and candidate selector.

This module compares original P50 QA scorecards with revised P52 pilot outputs.
It generates revised QA scorecards, before/after comparison records, and a local
production candidate shortlist before rendering, UI/API, deployment, upload, or
publishing work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.p50_creative_qa_engine import build_creative_qa_pack

P53_COMPARISON_VERSION = "p53.before_after_comparison.v1"
BEFORE_AFTER_FILENAME = "before_after_comparison.json"
CANDIDATE_SHORTLIST_FILENAME = "production_candidate_shortlist.json"
REPORT_FILENAME = "before_after_report.md"
REVISED_QA_FILENAME = "revised_qa_scorecards.json"


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object.")
    return data


def normalize_comparison_input(
    original_qa: dict[str, Any] | str | Path,
    revised_index: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Normalize original P50 QA pack and revised P52 index."""

    try:
        original = load_json(original_qa) if isinstance(original_qa, (str, Path)) else original_qa
        revised = load_json(revised_index) if isinstance(revised_index, (str, Path)) else revised_index
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"is_valid": False, "validation_errors": [str(exc)]}
    if not isinstance(original, dict) or not isinstance(original.get("scorecards"), list):
        return {"is_valid": False, "validation_errors": ["missing_original_scorecards"]}
    revised_entries = revised.get("revised_pilots") or revised.get("pilots") or revised.get("items") or []
    if not isinstance(revised_entries, list) or not revised_entries:
        return {"is_valid": False, "validation_errors": ["missing_revised_pilots"]}
    return {
        "is_valid": True,
        "original_qa": original,
        "revised_index": revised,
        "revised_entries": revised_entries,
    }


def revised_index_to_qa_source(revised_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert P52 revised index entries to the P50 QA input shape."""

    pilots = []
    for index, entry in enumerate(revised_entries, start=1):
        pilot_name = str(entry.get("revised_pilot_name") or entry.get("pilot_name") or f"revised-pilot-{index}")
        pilots.append({
            "pilot_number": index,
            "pilot_name": pilot_name,
            "topic": str(entry.get("topic") or "unknown topic"),
            "platform": str(entry.get("platform") or "unknown"),
            "output_dir": str(entry.get("revised_output_dir") or entry.get("output_dir") or ""),
            "is_valid": bool(entry.get("is_valid", True)),
            "pipeline_status": str(entry.get("pipeline_status") or "revise"),
            "rights_gate": str(entry.get("rights_gate") or "revise"),
            "engagement_score": _safe_int(entry.get("engagement_score"), 70),
            "monetization_status": str(entry.get("monetization_status") or "needs_packaging_improvement"),
            "production_ready": bool(entry.get("production_ready", bool(entry.get("revised_output_dir") or entry.get("output_dir")))),
            "template_platforms": list(entry.get("template_platforms") or []),
            "platform_templates_path": str(entry.get("platform_templates_path") or ""),
            "source_pilot_name": str(entry.get("source_pilot_name") or ""),
        })
    return {"pilots": pilots}


def build_before_after_comparison(
    original_qa: dict[str, Any] | str | Path,
    revised_index: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Build before/after comparison and candidate shortlist."""

    normalized = normalize_comparison_input(original_qa, revised_index)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P53_COMPARISON_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }
    revised_qa = build_creative_qa_pack(revised_index_to_qa_source(normalized["revised_entries"]))
    comparisons = compare_scorecards(
        normalized["original_qa"].get("scorecards", []),
        revised_qa.get("scorecards", []),
        normalized["revised_entries"],
    )
    shortlist = select_production_candidates(comparisons)
    return {
        "schema_version": P53_COMPARISON_VERSION,
        "is_valid": True,
        "revised_qa_scorecards": revised_qa,
        "comparisons": comparisons,
        "comparison_summary": build_comparison_summary(comparisons, shortlist),
        "production_candidate_shortlist": shortlist,
        "human_approval_required_before_production": True,
        **_guardrails(),
    }


def compare_scorecards(
    original_scorecards: list[dict[str, Any]],
    revised_scorecards: list[dict[str, Any]],
    revised_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    original_by_name = {str(item.get("pilot_name")): item for item in original_scorecards}
    revised_by_name = {str(item.get("pilot_name")): item for item in revised_scorecards}
    comparisons = []
    for entry in revised_entries:
        source_name = str(entry.get("source_pilot_name") or _strip_revised_suffix(str(entry.get("revised_pilot_name") or "")))
        revised_name = str(entry.get("revised_pilot_name") or entry.get("pilot_name") or f"{source_name}-revised")
        original = original_by_name.get(source_name, {})
        revised = revised_by_name.get(revised_name, {})
        original_score = _safe_int(original.get("weighted_overall_score"), 0)
        revised_score = _safe_int(revised.get("weighted_overall_score"), 0)
        delta = revised_score - original_score
        dimension_delta = compare_dimensions(original.get("baseline_scores", {}), revised.get("baseline_scores", {}))
        movement = movement_label(delta, original.get("recommendation"), revised.get("recommendation"))
        candidate_status = candidate_status_for(revised, delta, movement)
        comparisons.append({
            "source_pilot_name": source_name,
            "revised_pilot_name": revised_name,
            "topic": entry.get("topic") or revised.get("topic") or original.get("topic"),
            "platform": entry.get("platform") or revised.get("platform") or original.get("platform"),
            "original_score": original_score,
            "revised_score": revised_score,
            "score_delta": delta,
            "movement": movement,
            "original_recommendation": original.get("recommendation"),
            "revised_recommendation": revised.get("recommendation"),
            "dimension_deltas": dimension_delta,
            "biggest_gain": biggest_delta(dimension_delta, positive=True),
            "biggest_drop": biggest_delta(dimension_delta, positive=False),
            "candidate_status": candidate_status,
            "candidate_reason": candidate_reason(candidate_status, delta, revised),
            "original_output_dir": entry.get("original_output_dir", ""),
            "revised_output_dir": entry.get("revised_output_dir") or revised.get("output_dir", ""),
            "human_approval_required_before_production": True,
            "improvement_guaranteed": False,
        })
    return comparisons


def compare_dimensions(original_scores: dict[str, Any], revised_scores: dict[str, Any]) -> dict[str, int]:
    keys = sorted(set(original_scores) | set(revised_scores))
    return {key: _safe_int(revised_scores.get(key), 0) - _safe_int(original_scores.get(key), 0) for key in keys}


def movement_label(delta: int, original_recommendation: Any, revised_recommendation: Any) -> str:
    if revised_recommendation == "block":
        return "regressed" if original_recommendation != "block" else "unchanged"
    if delta >= 5:
        return "improved"
    if delta <= -5:
        return "regressed"
    return "unchanged"


def candidate_status_for(revised: dict[str, Any], delta: int, movement: str) -> str:
    recommendation = revised.get("recommendation")
    score = _safe_int(revised.get("weighted_overall_score"), 0)
    rights = _safe_int((revised.get("baseline_scores") or {}).get("rights_readiness"), 0)
    production = _safe_int((revised.get("baseline_scores") or {}).get("production_feasibility"), 0)
    if recommendation == "block" or rights < 65 or production < 65 or movement == "regressed":
        return "drop_or_rework"
    if score >= 82 and recommendation == "accept_for_human_review" and rights >= 80 and production >= 80:
        return "produce_after_human_approval"
    if delta >= 0:
        return "revise_again"
    return "drop_or_rework"


def candidate_reason(status: str, delta: int, revised: dict[str, Any]) -> str:
    if status == "produce_after_human_approval":
        return "Revised pilot is strong enough for human production approval."
    if status == "revise_again":
        return "Revised pilot improved or held steady but still needs creative tightening."
    if revised.get("recommendation") == "block":
        return "Revised pilot is still blocked by QA."
    if delta < 0:
        return "Revision regressed versus the original pilot."
    return "Rights, feasibility, or score is too weak for production."


def select_production_candidates(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    produce = [item for item in comparisons if item["candidate_status"] == "produce_after_human_approval"]
    revise = [item for item in comparisons if item["candidate_status"] == "revise_again"]
    drop = [item for item in comparisons if item["candidate_status"] == "drop_or_rework"]
    produce = sorted(produce, key=lambda item: (item["revised_score"], item["score_delta"]), reverse=True)
    return {
        "produce_after_human_approval": [candidate_view(item) for item in produce],
        "revise_again": [candidate_view(item) for item in revise],
        "drop_or_rework": [candidate_view(item) for item in drop],
        "human_approval_required_before_production": True,
    }


def candidate_view(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_pilot_name": item["source_pilot_name"],
        "revised_pilot_name": item["revised_pilot_name"],
        "platform": item["platform"],
        "revised_score": item["revised_score"],
        "score_delta": item["score_delta"],
        "movement": item["movement"],
        "candidate_reason": item["candidate_reason"],
        "revised_output_dir": item["revised_output_dir"],
        "human_approval_status": "pending",
    }


def build_comparison_summary(comparisons: list[dict[str, Any]], shortlist: dict[str, Any]) -> dict[str, Any]:
    improved = sum(1 for item in comparisons if item["movement"] == "improved")
    unchanged = sum(1 for item in comparisons if item["movement"] == "unchanged")
    regressed = sum(1 for item in comparisons if item["movement"] == "regressed")
    produce_count = len(shortlist["produce_after_human_approval"])
    if produce_count:
        decision = "review_production_candidates"
    elif improved or unchanged:
        decision = "revise_again_before_production"
    else:
        decision = "rework_pilot_strategy"
    return {
        "pilot_count": len(comparisons),
        "improved_count": improved,
        "unchanged_count": unchanged,
        "regressed_count": regressed,
        "production_candidate_count": produce_count,
        "batch_decision": decision,
        "next_actions": next_actions_for_decision(decision),
        "human_approval_required_before_production": True,
    }


def next_actions_for_decision(decision: str) -> list[str]:
    if decision == "review_production_candidates":
        return [
            "Human reviewer checks shortlisted pilots against brand, rights, and production budget.",
            "Approve one to three candidates for actual video production.",
            "Keep all rendering and publishing manual until approval is complete.",
        ]
    if decision == "revise_again_before_production":
        return [
            "Run another revision pass on pilots marked revise_again.",
            "Drop or rework weak pilots instead of spending on production.",
        ]
    return [
        "Revisit pilot topics, audience, and monetization route before another batch.",
        "Do not move to production until at least one candidate is approved.",
    ]


def write_before_after_files(
    original_qa: dict[str, Any] | str | Path,
    revised_index: dict[str, Any] | str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    result = build_before_after_comparison(original_qa, revised_index)
    if not result.get("is_valid"):
        return result
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    comparison_path = root / BEFORE_AFTER_FILENAME
    shortlist_path = root / CANDIDATE_SHORTLIST_FILENAME
    report_path = root / REPORT_FILENAME
    revised_qa_path = root / REVISED_QA_FILENAME
    comparison_path.write_text(_json_dump(result), encoding="utf-8")
    shortlist_path.write_text(_json_dump(result["production_candidate_shortlist"]), encoding="utf-8")
    revised_qa_path.write_text(_json_dump(result["revised_qa_scorecards"]), encoding="utf-8")
    report_path.write_text(render_report_markdown(result), encoding="utf-8")
    return {
        **result,
        "output_root": str(root),
        "before_after_comparison_path": str(comparison_path),
        "production_candidate_shortlist_path": str(shortlist_path),
        "revised_qa_scorecards_path": str(revised_qa_path),
        "before_after_report_path": str(report_path),
    }


def render_report_markdown(result: dict[str, Any]) -> str:
    summary = result["comparison_summary"]
    rows = "\n".join(
        f"| {item['source_pilot_name']} | {item['revised_pilot_name']} | {item['original_score']} | {item['revised_score']} | {item['score_delta']} | {item['movement']} | {item['candidate_status']} |"
        for item in result["comparisons"]
    )
    actions = "\n".join(f"- {action}" for action in summary["next_actions"])
    return f"""# Before/After QA Comparison

## Batch Decision

**{summary['batch_decision']}**

## Summary

- Pilots compared: {summary['pilot_count']}
- Improved: {summary['improved_count']}
- Unchanged: {summary['unchanged_count']}
- Regressed: {summary['regressed_count']}
- Production candidates: {summary['production_candidate_count']}

## Comparison Table

| Original | Revised | Original Score | Revised Score | Delta | Movement | Candidate Status |
|---|---|---:|---:|---:|---|---|
{rows}

## Next Actions

{actions}

## Guardrails

- Human approval is required before production.
- No rendering, upload, publishing, deployment, or external call was performed.
- Improvement and performance are not guaranteed.
"""


def biggest_delta(deltas: dict[str, int], *, positive: bool) -> dict[str, int] | None:
    if not deltas:
        return None
    key = max(deltas, key=deltas.get) if positive else min(deltas, key=deltas.get)
    return {key: deltas[key]}


def _strip_revised_suffix(name: str) -> str:
    return name[:-8] if name.endswith("-revised") else name


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "api_server_started": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "improvement_guaranteed": False,
        "performance_guaranteed": False,
        "human_approval_required_before_production": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare original and revised pilot QA locally.")
    parser.add_argument("original_qa", help="Path to P50 qa_scorecards.json")
    parser.add_argument("revised_index", help="Path to P52 revised_pilot_index.json")
    parser.add_argument("--output-root", default="outputs/revised-pilots", help="Local output root")
    args = parser.parse_args(argv)
    result = write_before_after_files(args.original_qa, args.revised_index, args.output_root)
    print(_json_dump(result))
    return 0 if result.get("is_valid") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
