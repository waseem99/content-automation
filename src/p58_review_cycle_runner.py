"""P58 one-command local review cycle runner.

This module stitches together the existing local creator review modules into one
operator command:

P55 original demo gallery -> P56 human feedback queue -> P57 revised gallery ->
P58 master summary/index/report.

It does not deploy, host a UI/API, render video, download assets, upload,
publish, call external services, or automate final production approval.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from src.p55_creator_demo_gallery import build_creator_demo_gallery
from src.p56_human_feedback_queue import write_feedback_outputs
from src.p57_feedback_regeneration_gallery import build_feedback_regeneration_gallery

P58_CYCLE_VERSION = "p58.one_command_local_review_cycle.v1"
SUMMARY_FILENAME = "review_cycle_summary.json"
INDEX_FILENAME = "review_cycle_index.html"
REPORT_FILENAME = "operator_run_report.md"
ORIGINAL_GALLERY_DIR = "original-gallery"
FEEDBACK_DIR = "feedback"
REGENERATION_DIR = "regeneration"

DEFAULT_BRIEFS_PATH = "docs/operations/p55-demo-briefs.json"
DEFAULT_FEEDBACK_PATH = "docs/operations/p56-review-feedback-template.json"


def run_local_review_cycle(
    demo_briefs: dict[str, Any] | str | Path,
    review_feedback: dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    include_rejected: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the full local content review cycle in one command."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    original_gallery = build_creator_demo_gallery(
        demo_briefs,
        root / ORIGINAL_GALLERY_DIR,
        overwrite=overwrite,
    )
    if not original_gallery.get("is_valid"):
        return invalid_step("original_gallery", root, original_gallery)

    feedback_outputs = write_feedback_outputs(
        original_gallery["demo_gallery_path"],
        review_feedback,
        root / FEEDBACK_DIR,
    )
    if not feedback_outputs.get("is_valid"):
        return invalid_step("feedback_queue", root, feedback_outputs)

    regeneration = build_feedback_regeneration_gallery(
        demo_briefs,
        feedback_outputs["review_feedback_summary_path"],
        root / REGENERATION_DIR,
        include_rejected=include_rejected,
        overwrite=overwrite,
    )
    if not regeneration.get("is_valid"):
        return invalid_step("feedback_regeneration", root, regeneration)

    summary = build_cycle_summary(root, original_gallery, feedback_outputs, regeneration)
    summary_path = root / SUMMARY_FILENAME
    index_path = root / INDEX_FILENAME
    report_path = root / REPORT_FILENAME
    summary_path.write_text(json_dump(summary), encoding="utf-8")
    index_path.write_text(render_cycle_index(summary), encoding="utf-8")
    report_path.write_text(render_operator_report(summary), encoding="utf-8")

    return {
        "schema_version": P58_CYCLE_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "review_cycle_summary_path": str(summary_path),
        "review_cycle_index_path": str(index_path),
        "operator_run_report_path": str(report_path),
        "original_gallery_index_path": original_gallery.get("gallery_index_path"),
        "feedback_report_path": feedback_outputs.get("review_feedback_report_path"),
        "revised_gallery_index_path": nested_get(regeneration, ["revised_gallery", "gallery_index_path"]),
        "demo_count": summary["counts"]["original_demo_count"],
        "revision_queue_count": summary["counts"]["revision_queue_count"],
        "revised_demo_count": summary["counts"]["revised_demo_count"],
        "human_review_required_before_production": True,
        **guardrails(),
    }


def invalid_step(step: str, root: Path, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": P58_CYCLE_VERSION,
        "is_valid": False,
        "failed_step": step,
        "output_root": str(root),
        "validation_errors": result.get("validation_errors", [f"{step}_failed"]),
        "step_result": result,
        **guardrails(),
    }


def build_cycle_summary(
    root: Path,
    original_gallery: dict[str, Any],
    feedback_outputs: dict[str, Any],
    regeneration: dict[str, Any],
) -> dict[str, Any]:
    feedback_summary = read_json(feedback_outputs.get("review_feedback_summary_path"))
    revised_gallery = regeneration.get("revised_gallery", {})
    counts = {
        "original_demo_count": int(original_gallery.get("demo_count", 0)),
        "successful_original_demo_count": int(original_gallery.get("successful_demo_count", 0)),
        "approved_count": int(feedback_outputs.get("approved_count", 0)),
        "revision_queue_count": int(feedback_outputs.get("revision_queue_count", 0)),
        "revised_demo_count": int(regeneration.get("revised_demo_count", 0)),
        "successful_revised_demo_count": int(revised_gallery.get("successful_demo_count", 0) or 0),
        "preserved_approved_count": int(regeneration.get("preserved_approved_count", 0)),
        "skipped_count": int(regeneration.get("skipped_count", 0)),
    }
    paths = {
        "output_root": str(root),
        "original_gallery_index": original_gallery.get("gallery_index_path"),
        "original_gallery_json": original_gallery.get("demo_gallery_path"),
        "feedback_summary_json": feedback_outputs.get("review_feedback_summary_path"),
        "revision_queue_json": feedback_outputs.get("revision_queue_path"),
        "feedback_report_md": feedback_outputs.get("review_feedback_report_path"),
        "revised_demo_briefs_json": regeneration.get("revised_demo_briefs_path"),
        "feedback_patch_summary_json": regeneration.get("feedback_patch_summary_path"),
        "regeneration_report_md": regeneration.get("feedback_regeneration_report_path"),
        "revised_gallery_index": nested_get(regeneration, ["revised_gallery", "gallery_index_path"]),
        "revised_gallery_json": nested_get(regeneration, ["revised_gallery", "demo_gallery_path"]),
    }
    next_actions = build_next_actions(counts)
    return {
        "schema_version": P58_CYCLE_VERSION,
        "is_valid": True,
        "cycle_status": "ready_for_human_review",
        "counts": counts,
        "paths": paths,
        "relative_links": {key: relative_href(root, value) for key, value in paths.items() if value},
        "feedback_summary": feedback_summary.get("summary", {}),
        "next_actions": next_actions,
        "human_review_required_before_production": True,
        **guardrails(),
    }


def build_next_actions(counts: dict[str, int]) -> list[str]:
    actions = [
        "Open review_cycle_index.html in a browser.",
        "Review the original gallery and revised gallery side by side.",
    ]
    if counts.get("revised_demo_count", 0):
        actions.append("Run human review on the revised gallery before production selection.")
    if counts.get("approved_count", 0):
        actions.append("Inspect approved candidates and confirm final production readiness manually.")
    actions.append("Do not upload, publish, or produce final video without human approval.")
    return actions


def render_cycle_index(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    links = summary.get("relative_links", {})
    action_items = "".join(f"<li>{esc(item)}</li>" for item in summary.get("next_actions", []))
    cards = [
        card("Original Gallery", "Review first-pass generated content packs.", links.get("original_gallery_index")),
        card("Feedback Report", "See approve, revise, reject decisions and revision queue.", links.get("feedback_report_md")),
        card("Revised Gallery", "Review feedback-patched regenerated content packs.", links.get("revised_gallery_index")),
        card("Regeneration Report", "See how feedback changed the revised briefs.", links.get("regeneration_report_md")),
        card("Cycle Summary JSON", "Machine-readable status and artifact map.", SUMMARY_FILENAME),
    ]
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Local Content Review Cycle</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #0f172a; }}
    header {{ padding: 34px 42px; background: linear-gradient(135deg, #0f172a, #1e293b); color: white; }}
    header h1 {{ margin: 0 0 8px; font-size: 32px; }}
    header p {{ margin: 0; color: #cbd5e1; max-width: 980px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 36px 52px; }}
    .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 18px; padding: 20px; box-shadow: 0 10px 26px rgba(15, 23, 42, .06); }}
    .span-3 {{ grid-column: span 3; }} .span-4 {{ grid-column: span 4; }} .span-8 {{ grid-column: span 8; }} .span-12 {{ grid-column: span 12; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; }}
    .metric {{ display: flex; justify-content: space-between; border-bottom: 1px solid #eef2f7; padding: 9px 0; gap: 12px; }}
    .metric:last-child {{ border-bottom: 0; }}
    .label {{ color: #64748b; }} .value {{ font-weight: 800; text-align: right; }}
    a {{ color: #2563eb; text-decoration: none; font-weight: 800; }} a:hover {{ text-decoration: underline; }}
    .notice {{ border-left: 4px solid #ca8a04; background: #fffbeb; color: #713f12; padding: 14px 16px; border-radius: 12px; }}
    ul {{ margin: 0; padding-left: 20px; }} li {{ margin: 7px 0; }}
    @media (max-width: 900px) {{ .span-3,.span-4,.span-8,.span-12 {{ grid-column: span 12; }} header, main {{ padding-left: 22px; padding-right: 22px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Local Content Review Cycle</h1>
    <p>One-command local review output: original gallery, human feedback queue, revised gallery, and operator report. Nothing was deployed, uploaded, rendered, or published.</p>
  </header>
  <main>
    <div class=\"grid\">
      <section class=\"card span-3\">{metric_block('Original demos', counts.get('original_demo_count'))}</section>
      <section class=\"card span-3\">{metric_block('Approved', counts.get('approved_count'))}</section>
      <section class=\"card span-3\">{metric_block('Revision queue', counts.get('revision_queue_count'))}</section>
      <section class=\"card span-3\">{metric_block('Revised demos', counts.get('revised_demo_count'))}</section>
      <section class=\"card span-8\">
        <h2>Open Review Outputs</h2>
        <div class=\"grid\">{''.join(cards)}</div>
      </section>
      <section class=\"card span-4\">
        <h2>Next Actions</h2>
        <ul>{action_items}</ul>
      </section>
      <section class=\"card span-12\">
        <p class=\"notice\">Human approval is required before production. This local cycle does not render video, download assets, upload, publish, deploy, call external services, or guarantee monetization/performance.</p>
      </section>
    </div>
  </main>
</body>
</html>
"""


def render_operator_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    paths = summary["paths"]
    lines = [
        "# Local Review Cycle Operator Report",
        "",
        "## Status",
        "- Cycle status: ready_for_human_review",
        "- Deployment performed: false",
        "- Upload/publish performed: false",
        "- Rendering performed: false",
        "- External calls performed: false",
        "- Human review required before production: true",
        "",
        "## Counts",
        f"- Original demos: {counts.get('original_demo_count', 0)}",
        f"- Approved candidates: {counts.get('approved_count', 0)}",
        f"- Revision queue items: {counts.get('revision_queue_count', 0)}",
        f"- Revised demos: {counts.get('revised_demo_count', 0)}",
        f"- Skipped items: {counts.get('skipped_count', 0)}",
        "",
        "## Key Outputs",
    ]
    for label, key in [
        ("Master index", "review_cycle_index"),
        ("Original gallery", "original_gallery_index"),
        ("Feedback report", "feedback_report_md"),
        ("Revised gallery", "revised_gallery_index"),
        ("Regeneration report", "regeneration_report_md"),
        ("Cycle summary", "review_cycle_summary"),
    ]:
        value = paths.get(key) or "generated at output root"
        lines.append(f"- {label}: {value}")
    lines.extend([
        "",
        "## Recommended Review Flow",
        *[f"- {item}" for item in summary.get("next_actions", [])],
        "",
        "## Guardrails",
        "No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or automated final approval is introduced.",
    ])
    return "\n".join(lines).strip() + "\n"


def card(title: str, description: str, href: str | None) -> str:
    link = f'<a href="{esc(href)}">Open</a>' if href else '<span class="label">Not available</span>'
    return f'<div class="card span-4"><h2>{esc(title)}</h2><p>{esc(description)}</p>{link}</div>'


def metric_block(label: str, value: Any) -> str:
    return f'<h2>{esc(label)}</h2><div class="metric"><span class="label">Count</span><span class="value">{esc(value)}</span></div>'


def read_json(path: Any) -> dict[str, Any]:
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def relative_href(root: Path, value: Any) -> str:
    try:
        return Path(str(value)).resolve().relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return str(value or "")


def nested_get(data: dict[str, Any], keys: list[str]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def guardrails() -> dict[str, Any]:
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
        "human_review_required_before_production": True,
    }


def cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "output_root": result.get("output_root"),
        "review_cycle_index_path": result.get("review_cycle_index_path"),
        "demo_count": result.get("demo_count", 0),
        "revision_queue_count": result.get("revision_queue_count", 0),
        "revised_demo_count": result.get("revised_demo_count", 0),
        "failed_step": result.get("failed_step"),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local creator review cycle end to end.")
    parser.add_argument("--demo-briefs", default=DEFAULT_BRIEFS_PATH, help="Path to P55 demo briefs JSON.")
    parser.add_argument("--feedback", default=DEFAULT_FEEDBACK_PATH, help="Path to P56 reviewer feedback JSON.")
    parser.add_argument("--output-root", default="outputs/review-cycle-demo", help="Local review cycle output root.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing local generated folders where supported.")
    parser.add_argument("--exclude-rejected", action="store_true", help="Do not regenerate rejected feedback items.")
    args = parser.parse_args(argv)
    try:
        result = run_local_review_cycle(
            args.demo_briefs,
            args.feedback,
            args.output_root,
            include_rejected=not args.exclude_rejected,
            overwrite=args.overwrite,
        )
        print(json_dump(cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
