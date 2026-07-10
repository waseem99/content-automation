"""P51 local pilot revision planner.

This module converts P50 creative QA scorecards into concrete revision packs.
It helps improve pilot video ideas before production, rendering, UI/API, or
cloud deployment work.

It does not deploy, render/edit video, download assets, upload, publish, call
external services, or replace human creative direction.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

P51_REVISION_VERSION = "p51.local_revision_plan.v1"
REVISION_PLAN_FILENAME = "revision_plan.json"
REVISION_SUMMARY_FILENAME = "revision_summary.md"
REVISION_PACK_DIRNAME = "revision_packs"
REVISED_BRIEF_DIRNAME = "revised_brief_patches"

DIMENSION_FIXES: dict[str, dict[str, str]] = {
    "hook_strength": {
        "task": "Rewrite the opening 1-3 seconds with a sharper contradiction, mistake, or outcome promise.",
        "brief_patch": "Add a stronger cold-open hook and remove any intro delay.",
        "acceptance": "The first line should make the target viewer stop scrolling without needing context.",
    },
    "clarity": {
        "task": "Simplify the core promise into one sentence and reduce competing ideas.",
        "brief_patch": "State the viewer problem, 3-step path, and payoff in plain language.",
        "acceptance": "A reviewer can explain the video promise after reading only the hook and title.",
    },
    "retention_potential": {
        "task": "Add clearer beat changes, pattern interrupts, and a visible payoff moment.",
        "brief_patch": "Add 4-6 retention beats with a payoff before the CTA.",
        "acceptance": "Every 3-5 seconds should introduce a new visual, step, proof point, or payoff.",
    },
    "platform_fit": {
        "task": "Adapt pacing, captions, CTA, and scene count to the primary platform.",
        "brief_patch": "Use platform-native pacing and caption direction instead of generic video structure.",
        "acceptance": "The revised brief should read as native to the selected platform.",
    },
    "originality": {
        "task": "Make the concept more specific and transformed; remove dependence on copied trends/IP.",
        "brief_patch": "Add original framing, own examples, and avoid borrowed characters/clips/logos.",
        "acceptance": "The video can be produced with owned/licensed assets and a distinct angle.",
    },
    "rights_readiness": {
        "task": "Resolve asset, music, likeness, logo, screenshot, and source risks before production.",
        "brief_patch": "Replace risky references with owned graphics, fictional examples, or licensed assets.",
        "acceptance": "Every required asset has an owned/licensed/source-evidence path.",
    },
    "monetization_fit": {
        "task": "Make the CTA useful, low-friction, and aligned with the monetization route.",
        "brief_patch": "Add a lead magnet, checklist, download, or soft conversion CTA after value delivery.",
        "acceptance": "The CTA should feel useful, not forced, and should match the target audience.",
    },
    "production_feasibility": {
        "task": "Reduce production complexity and make the required assets practical.",
        "brief_patch": "Prefer simple owned footage, editable graphics, screen mockups, and clear shot notes.",
        "acceptance": "An editor can produce the pilot using available or licensed assets only.",
    },
}


def load_qa_scorecards(path: str | Path) -> dict[str, Any]:
    """Load qa_scorecards.json from disk."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("scorecards"), list):
        raise ValueError("QA scorecards file must be an object with a scorecards list.")
    return data


def normalize_revision_input(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Normalize P50 QA pack or qa_scorecards.json path."""

    if isinstance(source, (str, Path)):
        source = load_qa_scorecards(source)
    if not isinstance(source, dict):
        return {"is_valid": False, "validation_errors": ["invalid_revision_source"]}
    scorecards = source.get("scorecards", [])
    if not scorecards:
        return {"is_valid": False, "validation_errors": ["missing_scorecards"]}
    normalized = []
    for index, scorecard in enumerate(scorecards, start=1):
        scores = scorecard.get("baseline_scores", {}) or {}
        normalized.append({
            "pilot_number": int(scorecard.get("pilot_number") or index),
            "pilot_name": str(scorecard.get("pilot_name") or f"pilot-{index}"),
            "topic": str(scorecard.get("topic") or "unknown topic"),
            "platform": str(scorecard.get("platform") or "unknown"),
            "output_dir": str(scorecard.get("output_dir") or ""),
            "baseline_scores": {key: _safe_int(scores.get(key), 70) for key in DIMENSION_FIXES},
            "weighted_overall_score": _safe_int(scorecard.get("weighted_overall_score"), 70),
            "recommendation": str(scorecard.get("recommendation") or "revise_before_production"),
            "top_issues": list(scorecard.get("top_issues") or []),
            "next_actions": list(scorecard.get("next_actions") or []),
        })
    return {
        "is_valid": True,
        "scorecards": normalized,
        "batch_summary": source.get("batch_summary", {}),
        "source_schema_version": source.get("schema_version"),
    }


def build_revision_plan(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Build per-pilot revision packs and batch summary."""

    normalized = normalize_revision_input(source)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P51_REVISION_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }
    pilots = [build_pilot_revision_pack(scorecard) for scorecard in normalized["scorecards"]]
    summary = build_batch_revision_summary(pilots)
    return {
        "schema_version": P51_REVISION_VERSION,
        "is_valid": True,
        "pilot_count": len(pilots),
        "revision_packs": pilots,
        "batch_revision_summary": summary,
        "human_approval_required_before_production": True,
        **_guardrails(),
    }


def build_pilot_revision_pack(scorecard: dict[str, Any]) -> dict[str, Any]:
    tasks = revision_tasks_for_scorecard(scorecard)
    priority = revision_priority(scorecard, tasks)
    patch = build_revised_brief_patch(scorecard, tasks, priority)
    return {
        "pilot_number": scorecard["pilot_number"],
        "pilot_name": scorecard["pilot_name"],
        "topic": scorecard["topic"],
        "platform": scorecard["platform"],
        "output_dir": scorecard["output_dir"],
        "source_recommendation": scorecard["recommendation"],
        "revision_priority": priority,
        "revision_tasks": tasks,
        "revised_brief_patch": patch,
        "acceptance_checks": acceptance_checks(tasks),
        "human_approval": {
            "reviewer": "",
            "status": "pending",
            "approved_for_next_generation": False,
            "notes": "",
        },
        "rendering_performed": False,
        "upload_or_publish_performed": False,
    }


def revision_tasks_for_scorecard(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    scores = scorecard["baseline_scores"]
    threshold = 82 if scorecard["recommendation"] == "accept_for_human_review" else 86
    for dimension, score in scores.items():
        if score < threshold or (scorecard["recommendation"] == "block" and dimension in {"rights_readiness", "production_feasibility"}):
            fix = DIMENSION_FIXES[dimension]
            tasks.append({
                "dimension": dimension,
                "score": score,
                "severity": severity_for_score(score, scorecard["recommendation"]),
                "task": fix["task"],
                "brief_patch": fix["brief_patch"],
                "acceptance_check": fix["acceptance"],
            })
    if not tasks:
        tasks.append({
            "dimension": "final_polish",
            "score": scorecard["weighted_overall_score"],
            "severity": "low",
            "task": "Run final human creative review and tighten wording before production.",
            "brief_patch": "Keep the core direction; polish title, hook, and CTA for the selected platform.",
            "acceptance_check": "Reviewer signs off before production.",
        })
    return tasks


def build_revised_brief_patch(scorecard: dict[str, Any], tasks: list[dict[str, Any]], priority: str) -> dict[str, Any]:
    dimensions = {task["dimension"] for task in tasks}
    topic = scorecard["topic"]
    platform = scorecard["platform"]
    return {
        "topic": topic,
        "platform": platform,
        "revision_goal": revision_goal(priority, topic),
        "hook_direction": hook_direction(topic, platform, dimensions),
        "script_direction": script_direction(dimensions),
        "storyboard_direction": storyboard_direction(dimensions, platform),
        "cta_direction": cta_direction(topic, dimensions),
        "rights_notes": rights_notes(dimensions),
        "production_notes": production_notes(dimensions),
        "must_add": [task["brief_patch"] for task in tasks],
        "must_avoid": [
            "Do not use unlicensed music, clips, screenshots, logos, or celebrity likeness.",
            "Do not claim guaranteed views, revenue, health outcomes, or savings.",
        ],
        "next_generation_ready": priority in {"low", "medium"},
        "human_approval_required": True,
    }


def build_batch_revision_summary(packs: list[dict[str, Any]]) -> dict[str, Any]:
    priorities = Counter(pack["revision_priority"] for pack in packs)
    dimensions = Counter(task["dimension"] for pack in packs for task in pack["revision_tasks"])
    if priorities.get("block"):
        decision = "block_until_critical_revisions_done"
    elif priorities.get("high") or priorities.get("medium", 0) >= 2:
        decision = "revise_then_regenerate_pilot_batch"
    else:
        decision = "ready_for_next_generation_after_human_review"
    return {
        "pilot_count": len(packs),
        "priority_counts": dict(priorities),
        "top_revision_themes": [name for name, _ in dimensions.most_common(5)],
        "batch_decision": decision,
        "next_actions": batch_next_actions(decision),
        "human_approval_required_before_production": True,
    }


def write_revision_files(source: dict[str, Any] | str | Path, output_root: str | Path) -> dict[str, Any]:
    plan = build_revision_plan(source)
    if not plan.get("is_valid"):
        return plan
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    pack_dir = root / REVISION_PACK_DIRNAME
    patch_dir = root / REVISED_BRIEF_DIRNAME
    pack_dir.mkdir(exist_ok=True)
    patch_dir.mkdir(exist_ok=True)
    written = []
    for pack in plan["revision_packs"]:
        slug = slugify(pack["pilot_name"])
        markdown_path = pack_dir / f"{slug}.md"
        patch_path = patch_dir / f"{slug}.json"
        markdown_path.write_text(render_revision_pack_markdown(pack), encoding="utf-8")
        patch_path.write_text(_json_dump(pack["revised_brief_patch"]), encoding="utf-8")
        written.extend([str(markdown_path), str(patch_path)])
    plan_path = root / REVISION_PLAN_FILENAME
    summary_path = root / REVISION_SUMMARY_FILENAME
    plan_path.write_text(_json_dump(plan), encoding="utf-8")
    summary_path.write_text(render_revision_summary_markdown(plan), encoding="utf-8")
    written.extend([str(plan_path), str(summary_path)])
    return {
        **plan,
        "output_root": str(root),
        "revision_plan_path": str(plan_path),
        "revision_summary_path": str(summary_path),
        "revision_pack_dir": str(pack_dir),
        "revised_brief_patch_dir": str(patch_dir),
        "written_files": written,
    }


def render_revision_pack_markdown(pack: dict[str, Any]) -> str:
    tasks = "\n".join(
        f"- **{task['dimension']}** ({task['severity']}, score {task['score']}): {task['task']}" for task in pack["revision_tasks"]
    )
    checks = "\n".join(f"- [ ] {item}" for item in pack["acceptance_checks"])
    patch = pack["revised_brief_patch"]
    return f"""# Revision Pack — {pack['pilot_name']}

## Status
- Topic: {pack['topic']}
- Platform: {pack['platform']}
- Priority: {pack['revision_priority']}
- Source recommendation: {pack['source_recommendation']}

## Revision Tasks
{tasks}

## Revised Brief Direction
- Goal: {patch['revision_goal']}
- Hook: {patch['hook_direction']}
- Script: {patch['script_direction']}
- Storyboard: {patch['storyboard_direction']}
- CTA: {patch['cta_direction']}
- Rights: {patch['rights_notes']}
- Production: {patch['production_notes']}

## Acceptance Checks
{checks}

## Human Approval
- Reviewer:
- Status: pending
- Approved for next generation: no
- Notes:
"""


def render_revision_summary_markdown(plan: dict[str, Any]) -> str:
    summary = plan["batch_revision_summary"]
    pilots = "\n".join(
        f"| {pack['pilot_name']} | {pack['platform']} | {pack['revision_priority']} | {len(pack['revision_tasks'])} |" for pack in plan["revision_packs"]
    )
    themes = "\n".join(f"- {theme}" for theme in summary["top_revision_themes"])
    actions = "\n".join(f"- {action}" for action in summary["next_actions"])
    return f"""# Batch Revision Summary

## Decision
{summary['batch_decision']}

## Pilot Revision Table
| Pilot | Platform | Priority | Tasks |
|---|---|---:|---:|
{pilots}

## Top Revision Themes
{themes}

## Next Actions
{actions}

Human approval is required before production.
"""


def acceptance_checks(tasks: list[dict[str, Any]]) -> list[str]:
    checks = [task["acceptance_check"] for task in tasks]
    checks.append("Human reviewer approves the revised direction before production.")
    return checks


def revision_priority(scorecard: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    if scorecard["recommendation"] == "block" or any(task["severity"] == "critical" for task in tasks):
        return "block"
    if scorecard["weighted_overall_score"] < 72 or any(task["severity"] == "high" for task in tasks):
        return "high"
    if scorecard["weighted_overall_score"] < 84 or len(tasks) >= 3:
        return "medium"
    return "low"


def severity_for_score(score: int, recommendation: str) -> str:
    if recommendation == "block" or score < 55:
        return "critical"
    if score < 70:
        return "high"
    if score < 82:
        return "medium"
    return "low"


def revision_goal(priority: str, topic: str) -> str:
    if priority == "block":
        return f"Resolve critical blockers before regenerating the {topic} pilot."
    if priority == "high":
        return f"Substantially revise the {topic} pilot before production review."
    if priority == "medium":
        return f"Tighten weak creative and packaging areas for {topic}."
    return f"Polish {topic} for final human review."


def hook_direction(topic: str, platform: str, dimensions: set[str]) -> str:
    if "hook_strength" in dimensions:
        return f"Open with a sharp platform-native claim: 'Most people get {topic} wrong because...'"
    return f"Keep the existing hook but make it native to {platform}."


def script_direction(dimensions: set[str]) -> str:
    if "clarity" in dimensions and "retention_potential" in dimensions:
        return "Rewrite into one problem, three steps, one proof/payoff, and one CTA."
    if "clarity" in dimensions:
        return "Simplify the script around one viewer problem and one promised outcome."
    if "retention_potential" in dimensions:
        return "Add stronger beat changes, visual proof, and an earlier payoff."
    return "Polish language and remove filler before production."


def storyboard_direction(dimensions: set[str], platform: str) -> str:
    if "platform_fit" in dimensions or "production_feasibility" in dimensions:
        return f"Rebuild storyboard with practical {platform} pacing, simple owned visuals, and clear caption-safe frames."
    return "Keep storyboard structure but improve frame specificity and caption alignment."


def cta_direction(topic: str, dimensions: set[str]) -> str:
    if "monetization_fit" in dimensions:
        return f"Use a useful CTA such as: 'Comment checklist for the {topic} worksheet.'"
    return "Keep CTA after value delivery; avoid hard selling."


def rights_notes(dimensions: set[str]) -> str:
    if "rights_readiness" in dimensions or "originality" in dimensions:
        return "Replace risky clips, logos, screenshots, music, likeness, and third-party examples with owned/licensed assets."
    return "Keep source evidence for every asset before production."


def production_notes(dimensions: set[str]) -> str:
    if "production_feasibility" in dimensions:
        return "Reduce complex shots; prefer owned footage, editable graphics, mockups, and licensed stock."
    return "Production can proceed after human creative and rights review."


def batch_next_actions(decision: str) -> list[str]:
    if decision == "block_until_critical_revisions_done":
        return [
            "Fix blocked pilots first, especially rights or production blockers.",
            "Regenerate revised briefs only after human approval.",
        ]
    if decision == "revise_then_regenerate_pilot_batch":
        return [
            "Apply revised brief patches.",
            "Regenerate local pilot folders.",
            "Run P50 QA again before production.",
        ]
    return [
        "Run final human review.",
        "Approve selected pilots for production planning.",
    ]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "pilot"


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        "human_approval_required_before_production": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local pilot revision packs from P50 QA scorecards.")
    parser.add_argument("qa_scorecards_json", help="Path to qa_scorecards.json.")
    parser.add_argument("--output-root", default=None, help="Output root for revision files. Defaults to qa file parent.")
    args = parser.parse_args(argv)
    try:
        output_root = args.output_root or str(Path(args.qa_scorecards_json).resolve().parent)
        result = write_revision_files(args.qa_scorecards_json, output_root)
        print(_json_dump({
            "ok": result.get("is_valid", False),
            "revision_plan_path": result.get("revision_plan_path"),
            "revision_summary_path": result.get("revision_summary_path"),
            "pilot_count": result.get("pilot_count", 0),
            "local_only": True,
        }), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
