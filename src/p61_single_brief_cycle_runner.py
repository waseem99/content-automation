"""P61 single-brief full local review cycle runner.

This module runs the current practical local creator workflow from one custom
brief JSON:

P60 adapter -> P58 local review cycle -> P61 master summary/index/report.

It remains local-only. It does not deploy, host a UI/API, render video,
download assets, upload, publish, call external services, or automate final
production approval.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from src.p58_review_cycle_runner import run_local_review_cycle
from src.p60_custom_brief_cycle_adapter import adapt_custom_brief

P61_CYCLE_VERSION = "p61.single_brief_full_review_cycle.v1"
ADAPTER_DIR = "adapter"
REVIEW_CYCLE_DIR = "review-cycle"
SUMMARY_FILENAME = "single_brief_cycle_summary.json"
INDEX_FILENAME = "single_brief_cycle_index.html"
REPORT_FILENAME = "single_brief_cycle_report.md"
DEFAULT_OUTPUT_ROOT = "outputs/single-brief-cycle"


def run_single_brief_cycle(
    brief_source: dict[str, Any] | str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the full local review cycle from one brief JSON."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    adapter_root = root / ADAPTER_DIR
    adapter = adapt_custom_brief(brief_source, adapter_root, overwrite=overwrite)
    if not adapter.get("is_valid"):
        return invalid_step("custom_brief_adapter", root, adapter)

    review_root = root / REVIEW_CYCLE_DIR
    review_cycle = run_local_review_cycle(
        adapter["custom_brief_library_path"],
        adapter["custom_feedback_template_path"],
        review_root,
        overwrite=overwrite,
    )
    if not review_cycle.get("is_valid"):
        return invalid_step("local_review_cycle", root, review_cycle)

    summary = build_single_brief_summary(root, adapter, review_cycle)
    summary_path = root / SUMMARY_FILENAME
    index_path = root / INDEX_FILENAME
    report_path = root / REPORT_FILENAME
    summary_path.write_text(json_dump(summary), encoding="utf-8")
    index_path.write_text(render_cycle_index(summary), encoding="utf-8")
    report_path.write_text(render_operator_report(summary), encoding="utf-8")

    return {
        "schema_version": P61_CYCLE_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "demo_slug": adapter.get("demo_slug"),
        "single_brief_cycle_summary_path": str(summary_path),
        "single_brief_cycle_index_path": str(index_path),
        "single_brief_cycle_report_path": str(report_path),
        "adapter_root": str(adapter_root),
        "review_cycle_root": str(review_root),
        "review_cycle_index_path": review_cycle.get("review_cycle_index_path"),
        "custom_brief_library_path": adapter.get("custom_brief_library_path"),
        "custom_feedback_template_path": adapter.get("custom_feedback_template_path"),
        "human_review_required_before_production": True,
        **guardrails(),
    }


def invalid_step(step: str, root: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Return a safe invalid result without continuing later steps."""

    return {
        "schema_version": P61_CYCLE_VERSION,
        "is_valid": False,
        "failed_step": step,
        "output_root": str(root),
        "validation_errors": result.get("validation_errors", [f"{step}_failed"]),
        "step_result": result,
        **guardrails(),
    }


def build_single_brief_summary(
    root: Path,
    adapter: dict[str, Any],
    review_cycle: dict[str, Any],
) -> dict[str, Any]:
    """Build the P61 master summary."""

    paths = {
        "output_root": str(root),
        "adapter_readme": adapter.get("custom_cycle_readme_path"),
        "adapter_manifest": adapter.get("custom_cycle_manifest_path"),
        "custom_brief_library": adapter.get("custom_brief_library_path"),
        "custom_feedback_template": adapter.get("custom_feedback_template_path"),
        "review_cycle_index": review_cycle.get("review_cycle_index_path"),
        "review_cycle_summary": review_cycle.get("review_cycle_summary_path"),
        "review_cycle_report": review_cycle.get("operator_run_report_path"),
        "original_gallery_index": review_cycle.get("original_gallery_index_path"),
        "feedback_report": review_cycle.get("feedback_report_path"),
        "revised_gallery_index": review_cycle.get("revised_gallery_index_path"),
    }
    counts = {
        "demo_count": int(review_cycle.get("demo_count", 0) or 0),
        "revision_queue_count": int(review_cycle.get("revision_queue_count", 0) or 0),
        "revised_demo_count": int(review_cycle.get("revised_demo_count", 0) or 0),
    }
    next_actions = [
        "Open single_brief_cycle_index.html in a browser.",
        "Open the full review cycle index and inspect the generated content pack.",
        "Replace placeholder feedback with real human review notes before production decisions.",
        "Re-run the cycle after updating feedback if another revision pass is needed.",
        "Do not upload, publish, or produce final video without human approval.",
    ]
    return {
        "schema_version": P61_CYCLE_VERSION,
        "is_valid": True,
        "cycle_status": "ready_for_human_review",
        "demo_slug": adapter.get("demo_slug"),
        "counts": counts,
        "paths": paths,
        "relative_links": {key: relative_href(root, value) for key, value in paths.items() if value},
        "next_actions": next_actions,
        "human_review_required_before_production": True,
        **guardrails(),
    }


def render_cycle_index(summary: dict[str, Any]) -> str:
    """Render a static local master index for the single-brief cycle."""

    counts = summary.get("counts", {})
    links = summary.get("relative_links", {})
    actions = "".join(f"<li>{esc(item)}</li>" for item in summary.get("next_actions", []))
    cards = [
        card("Full Review Cycle", "Open the complete generated review cycle.", links.get("review_cycle_index")),
        card("Adapter Readme", "See the generated custom brief adapter instructions.", links.get("adapter_readme")),
        card("Custom Brief Library", "One-item brief library produced from the source brief.", links.get("custom_brief_library")),
        card("Feedback Template", "Placeholder feedback file to replace after review.", links.get("custom_feedback_template")),
        card("Revised Gallery", "Open the feedback-driven revised gallery.", links.get("revised_gallery_index")),
        card("Cycle Summary JSON", "Machine-readable artifact map and counts.", SUMMARY_FILENAME),
    ]
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Single Brief Content Review Cycle</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #0f172a; }}
    header {{ padding: 34px 42px; background: linear-gradient(135deg, #111827, #1d4ed8); color: white; }}
    header h1 {{ margin: 0 0 8px; font-size: 32px; }}
    header p {{ margin: 0; color: #dbeafe; max-width: 980px; }}
    main {{ max-width: 1160px; margin: 0 auto; padding: 28px 36px 52px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 18px; }}
    .metric, .card, .notice {{ background: white; border: 1px solid #e2e8f0; border-radius: 18px; padding: 18px; box-shadow: 0 10px 26px rgba(15, 23, 42, .06); }}
    .metric span {{ display: block; color: #64748b; font-size: 13px; }}
    .metric strong {{ display: block; font-size: 30px; margin-top: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 20px; }}
    .card p {{ color: #64748b; }}
    a.button {{ display: inline-block; margin-top: 10px; padding: 10px 13px; border-radius: 12px; background: #2563eb; color: white; font-weight: 800; text-decoration: none; }}
    .notice {{ margin-top: 18px; border-left: 4px solid #ca8a04; background: #fffbeb; color: #713f12; }}
    ul {{ padding-left: 20px; }}
    @media (max-width: 900px) {{ .metrics, .grid {{ grid-template-columns: 1fr; }} header, main {{ padding-left: 20px; padding-right: 20px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Single Brief Content Review Cycle</h1>
    <p>One local brief has been adapted, processed through the review cycle, and packaged for human review. No deployment, rendering, upload, publish, or external call was performed.</p>
  </header>
  <main>
    <section class=\"metrics\">
      <div class=\"metric\"><span>Demo count</span><strong>{int(counts.get('demo_count', 0))}</strong></div>
      <div class=\"metric\"><span>Revision queue</span><strong>{int(counts.get('revision_queue_count', 0))}</strong></div>
      <div class=\"metric\"><span>Revised demos</span><strong>{int(counts.get('revised_demo_count', 0))}</strong></div>
    </section>
    <section class=\"grid\">{''.join(cards)}</section>
    <section class=\"notice\">
      <strong>Human review required.</strong>
      <ul>{actions}</ul>
    </section>
  </main>
</body>
</html>
"""


def card(title: str, description: str, href: str | None) -> str:
    button = f'<a class="button" href="{esc(href)}">Open</a>' if href else '<p>Unavailable</p>'
    return f"""
    <article class=\"card\">
      <h2>{esc(title)}</h2>
      <p>{esc(description)}</p>
      {button}
    </article>
    """


def render_operator_report(summary: dict[str, Any]) -> str:
    """Render a concise Markdown report for the operator."""

    paths = summary.get("paths", {})
    counts = summary.get("counts", {})
    lines = [
        "# Single Brief Cycle Report",
        "",
        f"Demo slug: `{summary.get('demo_slug')}`",
        "",
        "## Counts",
        f"- Demo count: {counts.get('demo_count', 0)}",
        f"- Revision queue count: {counts.get('revision_queue_count', 0)}",
        f"- Revised demo count: {counts.get('revised_demo_count', 0)}",
        "",
        "## Open first",
        f"- Master index: `{INDEX_FILENAME}`",
        f"- Full review cycle index: `{paths.get('review_cycle_index')}`",
        "",
        "## Review instructions",
        "- Open the full review cycle index and inspect the generated content pack.",
        "- Replace placeholder feedback with real human review notes before production decisions.",
        "- Re-run the cycle after feedback changes if another revision pass is needed.",
        "- Do not upload, publish, or produce final video without human approval.",
        "",
        "## Guardrails",
        "No deployment, hosted UI/API, rendering, asset download, upload, publishing, external calls, or automated final production approval was performed.",
        "",
    ]
    return "\n".join(lines)


def relative_href(root: Path, target: Any) -> str:
    if not target:
        return ""
    try:
        return Path(str(target)).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(str(target)).name


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


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
        "browser_command_execution": False,
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
        "index": result.get("single_brief_cycle_index_path"),
        "review_cycle_index": result.get("review_cycle_index_path"),
        "demo_slug": result.get("demo_slug"),
        "local_only": result.get("local_only", True),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a full local content review cycle from one brief JSON.")
    parser.add_argument("brief_json", help="Path to one Creator Studio/custom brief JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Local output root for the single-brief cycle.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing local cycle files.")
    args = parser.parse_args(argv)
    try:
        result = run_single_brief_cycle(args.brief_json, args.output_root, overwrite=args.overwrite)
        print(json_dump(cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
