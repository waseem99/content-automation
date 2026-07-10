"""P52 local revised pilot regeneration runner.

This module applies P51 revision patches to original P49 pilot briefs and runs a
second local generation pass. It is designed to compare revised pilot outputs
before any UI/API, deployment, rendering, upload, or publishing work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.p47_local_folder_runner import run_local_folder_export
from src.p48_platform_template_engine import build_platform_template_pack
from src.p49_pilot_batch_runner import load_pilot_briefs

P52_REGEN_VERSION = "p52.revised_pilot_regeneration.v1"
REVISED_INDEX_FILENAME = "revised_pilot_index.json"
REVISED_SUMMARY_FILENAME = "revised_generation_summary.md"
PLATFORM_TEMPLATE_FILENAME = "platform_templates.json"
REVISED_BRIEFS_FILENAME = "revised_pilot_briefs.json"


def load_revision_plan(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("revision_packs"), list):
        raise ValueError("Revision plan must be an object with a revision_packs list.")
    return data


def load_briefs_source(source: list[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(source, (str, Path)):
        return load_pilot_briefs(source)
    if isinstance(source, list) and all(isinstance(item, dict) for item in source):
        return source
    raise ValueError("Pilot briefs must be a list of brief objects or a JSON path.")


def normalize_regeneration_input(
    pilot_briefs: list[dict[str, Any]] | str | Path,
    revision_plan: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Normalize original pilot briefs and P51 revision plan."""

    try:
        briefs = load_briefs_source(pilot_briefs)
        plan = load_revision_plan(revision_plan) if isinstance(revision_plan, (str, Path)) else revision_plan
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"is_valid": False, "validation_errors": [str(exc)]}
    if not briefs:
        return {"is_valid": False, "validation_errors": ["missing_pilot_briefs"]}
    if not isinstance(plan, dict) or not isinstance(plan.get("revision_packs"), list):
        return {"is_valid": False, "validation_errors": ["missing_revision_packs"]}
    brief_map = {str(brief.get("pilot_name") or f"pilot-{idx}"): brief for idx, brief in enumerate(briefs, start=1)}
    packs = {str(pack.get("pilot_name") or f"pilot-{idx}"): pack for idx, pack in enumerate(plan.get("revision_packs", []), start=1)}
    missing = sorted(name for name in packs if name not in brief_map)
    return {
        "is_valid": not missing,
        "validation_errors": [f"missing_original_brief:{name}" for name in missing],
        "briefs": brief_map,
        "revision_packs": packs,
        "source_revision_schema": plan.get("schema_version"),
    }


def apply_revised_brief_patch(original_brief: dict[str, Any], revision_pack: dict[str, Any]) -> dict[str, Any]:
    """Apply a P51 revised brief patch while preserving core brief identity."""

    patch = revision_pack.get("revised_brief_patch", {}) or {}
    source_name = str(original_brief.get("pilot_name") or revision_pack.get("pilot_name") or "pilot")
    revised = dict(original_brief)
    revised["pilot_name"] = f"{source_name}-revised"
    revised["topic"] = original_brief.get("topic") or patch.get("topic")
    revised["platform"] = original_brief.get("platform") or patch.get("platform")
    revised["audience"] = original_brief.get("audience")
    revised["monetization_goal"] = original_brief.get("monetization_goal")
    revised["revision_source"] = {
        "source_pilot_name": source_name,
        "revision_priority": revision_pack.get("revision_priority"),
        "source_recommendation": revision_pack.get("source_recommendation"),
        "applied_task_count": len(revision_pack.get("revision_tasks", [])),
    }
    revised["revision_goal"] = patch.get("revision_goal")
    revised["revised_hook_direction"] = patch.get("hook_direction")
    revised["revised_script_direction"] = patch.get("script_direction")
    revised["revised_storyboard_direction"] = patch.get("storyboard_direction")
    revised["revised_cta_direction"] = patch.get("cta_direction")
    revised["revised_rights_notes"] = patch.get("rights_notes")
    revised["revised_production_notes"] = patch.get("production_notes")
    revised["must_use_points"] = _dedupe_list(
        list(original_brief.get("must_use_points") or [])
        + list(patch.get("must_add") or [])
        + [item for item in [patch.get("hook_direction"), patch.get("script_direction"), patch.get("cta_direction")] if item]
    )
    revised["avoid"] = _dedupe_list(list(original_brief.get("avoid") or []) + list(patch.get("must_avoid") or []))
    revised["source_notes"] = _dedupe_list(
        list(original_brief.get("source_notes") or [])
        + [item for item in [patch.get("rights_notes"), patch.get("production_notes")] if item]
    )
    revised["human_approval_required_before_production"] = True
    return revised


def run_revised_regeneration(
    pilot_briefs: list[dict[str, Any]] | str | Path,
    revision_plan: dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the second-generation local output pass for revised pilot briefs."""

    normalized = normalize_regeneration_input(pilot_briefs, revision_plan)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P52_REGEN_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    revised_briefs = []
    entries = []
    for pilot_name, revision_pack in normalized["revision_packs"].items():
        original = normalized["briefs"][pilot_name]
        revised = apply_revised_brief_patch(original, revision_pack)
        revised_briefs.append(revised)
        export_result = run_local_folder_export(revised, root, overwrite=overwrite)
        template_path = ""
        template_platforms: list[str] = []
        if export_result.get("is_valid"):
            output_dir = Path(export_result["output_dir"])
            template_pack = build_platform_template_pack(revised)
            template_path = str(write_platform_templates(output_dir, template_pack))
            template_platforms = sorted(template_pack.get("templates", {}).keys())
        entries.append(build_comparison_entry(pilot_name, original, revised, revision_pack, export_result, template_path, template_platforms))
    revised_briefs_path = root / REVISED_BRIEFS_FILENAME
    index_path = root / REVISED_INDEX_FILENAME
    summary_path = root / REVISED_SUMMARY_FILENAME
    index_payload = build_revised_index(entries, revised_briefs_path)
    revised_briefs_path.write_text(_json_dump({"schema_version": "p52.revised_pilot_briefs.v1", "briefs": revised_briefs}), encoding="utf-8")
    index_path.write_text(_json_dump(index_payload), encoding="utf-8")
    summary_path.write_text(render_revised_summary(index_payload), encoding="utf-8")
    return {
        "schema_version": P52_REGEN_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "revised_pilot_count": len(entries),
        "successful_revised_pilots": sum(1 for item in entries if item["is_valid"]),
        "revised_pilot_index_path": str(index_path),
        "revised_generation_summary_path": str(summary_path),
        "revised_pilot_briefs_path": str(revised_briefs_path),
        "revised_pilots": entries,
        **_guardrails(),
    }


def write_platform_templates(output_dir: Path, template_pack: dict[str, Any]) -> Path:
    path = output_dir / PLATFORM_TEMPLATE_FILENAME
    path.write_text(_json_dump(template_pack), encoding="utf-8")
    return path


def build_comparison_entry(
    original_name: str,
    original: dict[str, Any],
    revised: dict[str, Any],
    revision_pack: dict[str, Any],
    export_result: dict[str, Any],
    template_path: str,
    template_platforms: list[str],
) -> dict[str, Any]:
    return {
        "source_pilot_name": original_name,
        "revised_pilot_name": revised.get("pilot_name"),
        "topic": original.get("topic"),
        "platform": original.get("platform"),
        "revision_priority": revision_pack.get("revision_priority"),
        "source_recommendation": revision_pack.get("source_recommendation"),
        "applied_patch_count": len(revision_pack.get("revision_tasks", [])),
        "original_output_dir": revision_pack.get("output_dir") or original.get("output_dir", ""),
        "revised_output_dir": export_result.get("output_dir", ""),
        "platform_templates_path": template_path,
        "template_platforms": template_platforms,
        "is_valid": bool(export_result.get("is_valid")),
        "pipeline_status": export_result.get("summary", {}).get("pipeline_status"),
        "rights_gate": export_result.get("summary", {}).get("rights_gate"),
        "engagement_score": export_result.get("summary", {}).get("engagement_score"),
        "monetization_status": export_result.get("summary", {}).get("monetization_status"),
        "human_review_required_before_production": True,
        "improvement_guaranteed": False,
    }


def build_revised_index(entries: list[dict[str, Any]], revised_briefs_path: Path) -> dict[str, Any]:
    priorities: dict[str, int] = {}
    for entry in entries:
        priority = str(entry.get("revision_priority") or "unknown")
        priorities[priority] = priorities.get(priority, 0) + 1
    return {
        "schema_version": "p52.revised_pilot_index.v1",
        "revised_pilot_count": len(entries),
        "successful_revised_pilots": sum(1 for item in entries if item["is_valid"]),
        "revision_priority_counts": priorities,
        "revised_pilot_briefs_path": str(revised_briefs_path),
        "revised_pilots": entries,
        "human_review_required_before_production": True,
        "improvement_guaranteed": False,
        **_guardrails(),
    }


def render_revised_summary(index: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {item['source_pilot_name']} | {item['revised_pilot_name']} | {item['revision_priority']} | {item['applied_patch_count']} | {item['pipeline_status']} | {item['revised_output_dir']} |"
        for item in index.get("revised_pilots", [])
    )
    return f"""# Revised Pilot Generation Summary

## Batch result

- Revised pilots: {index['revised_pilot_count']}
- Successful revised pilots: {index['successful_revised_pilots']}
- Human review required before production: yes
- Improvement guaranteed: no

## Before / after index

| Original | Revised | Priority | Patches | Pipeline Status | Revised Output |
|---|---|---:|---:|---|---|
{rows}

## Next step

Review the revised folders and compare them against the original P49/P50/P51 outputs before creating actual videos.
"""


def _dedupe_list(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, bool]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "api_server_started": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "improvement_guaranteed": False,
        "human_review_required_before_production": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run revised pilot regeneration locally.")
    parser.add_argument("pilot_briefs_json", help="Path to original pilot brief library JSON.")
    parser.add_argument("revision_plan_json", help="Path to P51 revision_plan.json.")
    parser.add_argument("--output-root", default="outputs/revised-pilots", help="Local output root.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing pilot folders.")
    args = parser.parse_args(argv)
    result = run_revised_regeneration(args.pilot_briefs_json, args.revision_plan_json, args.output_root, overwrite=args.overwrite)
    sys.stdout.write(_json_dump(result))
    return 0 if result.get("is_valid") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
