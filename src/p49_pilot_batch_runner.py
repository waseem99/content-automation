"""P49 real pilot content batch runner.

This module runs multiple realistic pilot briefs through the local production
folder workflow and adds platform-specific templates for each pilot. It is meant
for manual creative review before any UI, API, deployment, rendering, upload, or
publishing work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.p47_local_folder_runner import run_local_folder_export
from src.p48_platform_template_engine import build_platform_template_pack

P49_BATCH_VERSION = "p49.real_pilot_batch_runner.v1"
PILOT_INDEX_FILENAME = "pilot_index.json"
PILOT_REVIEW_FILENAME = "pilot_review_checklist.md"
PLATFORM_TEMPLATE_FILENAME = "platform_templates.json"

DEFAULT_PILOT_BRIEFS: list[dict[str, Any]] = [
    {
        "pilot_name": "ai-automation-founder-short",
        "topic": "AI automation for small business owners",
        "platform": "youtube_shorts",
        "audience": "busy founders who want practical automation wins",
        "tone": "sharp, useful, cinematic",
        "duration_seconds": 45,
        "monetization_goal": "newsletter signups and SaaS affiliate revenue",
        "content_format": "vertical_short",
        "must_use_points": ["show one workflow", "avoid hype", "make it practical"],
        "avoid": ["celebrity voice", "movie clip", "unlicensed software screenshots"],
        "source_notes": ["Use owned mockups, original narration, and licensed music only."],
    },
    {
        "pilot_name": "travel-budget-mistakes-reel",
        "topic": "budget travel mistakes first-time Dubai visitors make",
        "platform": "instagram_reels",
        "audience": "young travelers planning their first Dubai trip",
        "tone": "fast, visual, friendly",
        "duration_seconds": 35,
        "monetization_goal": "travel checklist lead magnet and affiliate hotel links",
        "content_format": "vertical_short",
        "must_use_points": ["show 3 mistakes", "include one money-saving tip", "end with checklist CTA"],
        "avoid": ["hotel logos", "airline logos", "unlicensed destination footage"],
        "source_notes": ["Use owned clips, licensed stock, or original map-style graphics."],
    },
    {
        "pilot_name": "fitness-meal-prep-tiktok",
        "topic": "meal prep system for busy professionals trying to lose fat",
        "platform": "tiktok",
        "audience": "busy professionals who fail diets because of time pressure",
        "tone": "direct, practical, motivating",
        "duration_seconds": 30,
        "monetization_goal": "meal plan download and coaching enquiry",
        "content_format": "vertical_short",
        "must_use_points": ["show a simple 3-container system", "avoid extreme claims", "make it saveable"],
        "avoid": ["medical claims", "before-after body photos", "celebrity trainer references"],
        "source_notes": ["Use original food prep footage or licensed stock; add health disclaimer in review."],
    },
    {
        "pilot_name": "used-car-import-guide-short",
        "topic": "Japanese used car import checklist for overseas buyers",
        "platform": "youtube_shorts",
        "audience": "first-time overseas buyers comparing Japanese auction cars",
        "tone": "trust-building, clear, premium",
        "duration_seconds": 50,
        "monetization_goal": "qualified WhatsApp leads and buyer guide downloads",
        "content_format": "vertical_short",
        "must_use_points": ["explain inspection sheet", "mention payment trust", "show buyer checklist"],
        "avoid": ["specific third-party auction screenshots", "brand logos as decoration", "guaranteed savings claims"],
        "source_notes": ["Use owned sample checklist graphics and licensed generic car footage."],
    },
    {
        "pilot_name": "cybersecurity-phishing-longform",
        "topic": "phishing red flags every small team should know",
        "platform": "youtube_long",
        "audience": "small business owners and operations managers",
        "tone": "calm, expert, non-technical",
        "duration_seconds": 420,
        "monetization_goal": "security audit enquiries and checklist download",
        "content_format": "longform",
        "must_use_points": ["show fake email anatomy", "include team checklist", "avoid fearmongering"],
        "avoid": ["real breached emails", "brand impersonation", "live malicious links"],
        "source_notes": ["Use fictional emails and original diagrams only."],
    },
]


def load_pilot_briefs(path: str | Path) -> list[dict[str, Any]]:
    """Load pilot briefs from local JSON list or {"briefs": [...]} object."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("briefs")
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("Pilot brief JSON must be a list of objects or an object with a briefs list.")
    return data


def validate_pilot_briefs(briefs: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not briefs:
        errors.append("missing_pilot_briefs")
    required = ["topic", "platform", "audience", "monetization_goal"]
    for index, brief in enumerate(briefs, start=1):
        for field in required:
            if not str(brief.get(field, "")).strip():
                errors.append(f"pilot_{index}_missing_{field}")
    return errors


def run_pilot_batch(
    briefs: list[dict[str, Any]],
    output_root: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run multiple pilots locally and write batch index/review files."""

    validation_errors = validate_pilot_briefs(briefs)
    if validation_errors:
        return {
            "schema_version": P49_BATCH_VERSION,
            "is_valid": False,
            "validation_errors": validation_errors,
            **_guardrails(),
        }
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    pilots: list[dict[str, Any]] = []
    for index, brief in enumerate(briefs, start=1):
        pilot_result = run_local_folder_export(brief, root, overwrite=overwrite)
        pilot_entry = build_pilot_entry(index, brief, pilot_result)
        if pilot_result.get("is_valid"):
            template_pack = build_platform_template_pack(brief)
            template_path = write_platform_templates(Path(pilot_result["output_dir"]), template_pack)
            update_pilot_manifest(Path(pilot_result["output_dir"]), template_path)
            pilot_entry["platform_templates_path"] = str(template_path)
            pilot_entry["template_platforms"] = sorted(template_pack.get("templates", {}).keys())
        pilots.append(pilot_entry)
    index_payload = build_pilot_index(pilots)
    review_text = render_pilot_review_checklist(pilots)
    index_path = root / PILOT_INDEX_FILENAME
    review_path = root / PILOT_REVIEW_FILENAME
    index_path.write_text(_json_dump(index_payload), encoding="utf-8")
    review_path.write_text(review_text, encoding="utf-8")
    return {
        "schema_version": P49_BATCH_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "pilot_count": len(pilots),
        "successful_pilots": sum(1 for item in pilots if item["is_valid"]),
        "pilots": pilots,
        "pilot_index_path": str(index_path),
        "pilot_review_checklist_path": str(review_path),
        **_guardrails(),
    }


def build_pilot_entry(index: int, brief: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary", {})
    return {
        "pilot_number": index,
        "pilot_name": brief.get("pilot_name") or f"pilot-{index:02d}",
        "topic": brief.get("topic"),
        "platform": brief.get("platform"),
        "is_valid": bool(result.get("is_valid")),
        "output_dir": result.get("output_dir"),
        "pipeline_status": summary.get("pipeline_status"),
        "rights_gate": summary.get("rights_gate"),
        "engagement_score": summary.get("engagement_score"),
        "monetization_status": summary.get("monetization_status"),
        "next_actions": summary.get("next_actions", []),
        "file_count": result.get("file_count", 0),
    }


def write_platform_templates(output_dir: Path, template_pack: dict[str, Any]) -> Path:
    target = output_dir / PLATFORM_TEMPLATE_FILENAME
    target.write_text(_json_dump(template_pack), encoding="utf-8")
    return target


def update_pilot_manifest(output_dir: Path, template_path: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        return
    manifest = [item for item in manifest if item.get("filename") != PLATFORM_TEMPLATE_FILENAME]
    manifest.append({
        "filename": PLATFORM_TEMPLATE_FILENAME,
        "path": str(template_path),
        "content_type": "application/json",
        "bytes": template_path.stat().st_size,
        "local_only": True,
    })
    manifest_path.write_text(_json_dump(sorted(manifest, key=lambda item: item["filename"])), encoding="utf-8")


def build_pilot_index(pilots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "p49.pilot_index.v1",
        "pilot_count": len(pilots),
        "successful_pilots": sum(1 for item in pilots if item["is_valid"]),
        "pilots": pilots,
        **_guardrails(),
    }


def render_pilot_review_checklist(pilots: list[dict[str, Any]]) -> str:
    lines = [
        "# Pilot Review Checklist",
        "",
        "Use this before any production, rendering, upload, or deployment.",
        "",
    ]
    for pilot in pilots:
        lines.extend([
            f"## Pilot {pilot['pilot_number']} — {pilot['pilot_name']}",
            f"- Topic: {pilot.get('topic')}",
            f"- Platform: {pilot.get('platform')}",
            f"- Output: {pilot.get('output_dir')}",
            f"- Status: {pilot.get('pipeline_status')}",
            f"- Rights gate: {pilot.get('rights_gate')}",
            f"- Engagement score: {pilot.get('engagement_score')}",
            "- [ ] Hook is strong enough for the platform",
            "- [ ] Script has a clear payoff",
            "- [ ] Storyboard is visually executable",
            "- [ ] Assets are owned/licensed or easy to create",
            "- [ ] Platform template feels native",
            "- [ ] Producer can create this without extra clarification",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local pilot video content folders.")
    parser.add_argument("pilot_json", nargs="?", help="Optional path to pilot brief list JSON.")
    parser.add_argument("--output-root", default="outputs/pilots", help="Local output root.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing pilot folders.")
    args = parser.parse_args(argv)
    try:
        briefs = load_pilot_briefs(args.pilot_json) if args.pilot_json else DEFAULT_PILOT_BRIEFS
        result = run_pilot_batch(briefs, args.output_root, overwrite=args.overwrite)
        print(_json_dump({
            "ok": result.get("is_valid", False),
            "output_root": result.get("output_root"),
            "pilot_count": result.get("pilot_count", 0),
            "successful_pilots": result.get("successful_pilots", 0),
            "pilot_index_path": result.get("pilot_index_path"),
            "local_only": result.get("local_only", True),
        }), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "api_server_started": False,
        "trend_scraping_performed": False,
        "platform_api_called": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "performance_guaranteed": False,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
