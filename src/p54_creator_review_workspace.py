"""P54 local content creator review workspace.

This module turns one video brief into a browser-openable local review folder.
It reuses the local pipeline/export stack and adds a static `index.html` plus
`creator_review.json` so a human can inspect the content pack before production.

It does not deploy, host an API/UI, render video, download assets, upload,
publish, call external services, or guarantee monetization/performance.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

from src.p46_local_export_pack import build_local_export_pack
from src.p47_local_folder_runner import load_brief_json, run_local_folder_export

P54_WORKSPACE_VERSION = "p54.local_creator_review_workspace.v1"
CREATOR_REVIEW_FILENAME = "creator_review.json"
INDEX_FILENAME = "index.html"

EXPECTED_REVIEW_FILES = [
    "producer_brief.md",
    "script.txt",
    "storyboard.md",
    "shot_list.csv",
    "captions.srt",
    "metadata.json",
    "asset_manifest.json",
    "review_checklist.md",
    "platform_variants.json",
    "manifest.json",
    "summary.json",
]

REVIEW_CHECKLIST = [
    "Hook is strong enough to stop the target viewer.",
    "Promise is clear within the first few seconds.",
    "Idea feels specific and not generic filler.",
    "Storyboard is usable by an editor.",
    "Shot list is practical with owned or licensed assets.",
    "Captions are readable and platform-native.",
    "Rights notes do not show unresolved high-risk dependencies.",
    "Monetization route and CTA feel natural after value delivery.",
]

DECISION_OPTIONS = ["approve_for_production", "revise", "reject"]


def build_creator_review_workspace(
    brief_source: dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    project_slug: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate local export files plus a static creator review workspace."""

    try:
        brief = load_brief_json(brief_source) if isinstance(brief_source, (str, Path)) else brief_source
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _invalid([str(exc)])
    if not isinstance(brief, dict):
        return _invalid(["brief_must_be_object"])

    export_pack = build_local_export_pack(brief)
    if not export_pack.get("is_valid"):
        return _invalid(export_pack.get("validation_errors", ["invalid_export_pack"]), export_pack=export_pack)

    try:
        export_result = run_local_folder_export(
            brief,
            output_root,
            project_slug=project_slug,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        return _invalid([str(exc)], export_pack=export_pack)

    if not export_result.get("is_valid"):
        return _invalid(export_result.get("validation_errors", ["invalid_local_export"]), export_pack=export_pack)

    project_dir = Path(export_result["output_dir"]).resolve()
    _assert_within_root(Path(output_root).expanduser().resolve(), project_dir)
    review = build_creator_review_summary(brief, export_pack, project_dir)
    review_path = project_dir / CREATOR_REVIEW_FILENAME
    html_path = project_dir / INDEX_FILENAME
    review_path.write_text(_json_dump(review), encoding="utf-8")
    html_path.write_text(render_review_workspace_html(review, project_dir), encoding="utf-8")

    return {
        "schema_version": P54_WORKSPACE_VERSION,
        "is_valid": True,
        "output_dir": str(project_dir),
        "index_html_path": str(html_path),
        "creator_review_path": str(review_path),
        "project_slug": export_result.get("project_slug"),
        "file_count": len(export_result.get("written_files", [])) + 2,
        "review_decision_options": DECISION_OPTIONS,
        "human_review_required_before_production": True,
        **_guardrails(),
    }


def build_creator_review_summary(
    brief: dict[str, Any],
    export_pack: dict[str, Any],
    project_dir: Path,
) -> dict[str, Any]:
    """Build creator-facing summary JSON for the HTML review page."""

    pipeline = export_pack.get("pipeline_package", {})
    video = pipeline.get("video_package", {}) if isinstance(pipeline, dict) else {}
    normalized_brief = video.get("brief", {}) if isinstance(video, dict) else {}
    summary = pipeline.get("summary", {}) if isinstance(pipeline, dict) else {}
    rights_report = pipeline.get("rights_report", {}) if isinstance(pipeline, dict) else {}
    monetization_report = pipeline.get("monetization_report", {}) if isinstance(pipeline, dict) else {}
    production_pack = pipeline.get("production_pack", {}) if isinstance(pipeline, dict) else {}
    engagement = pipeline.get("engagement_scorecard", {}) if isinstance(pipeline, dict) else {}

    return {
        "schema_version": P54_WORKSPACE_VERSION,
        "project": {
            "topic": normalized_brief.get("topic") or brief.get("topic"),
            "platform": normalized_brief.get("platform") or brief.get("platform"),
            "audience": normalized_brief.get("audience") or brief.get("audience"),
            "tone": normalized_brief.get("tone") or brief.get("tone"),
            "duration_seconds": normalized_brief.get("duration_seconds") or brief.get("duration_seconds"),
            "monetization_goal": normalized_brief.get("monetization_goal") or brief.get("monetization_goal"),
            "output_dir": str(project_dir),
        },
        "creative": {
            "selected_concept": video.get("selected_concept") or first_item(video.get("concepts")),
            "title_options": video.get("title_options") or video.get("titles") or [],
            "hook": video.get("hook", ""),
            "script_preview": preview_text(_read_optional(project_dir / "script.txt") or video.get("script", ""), 1200),
            "storyboard_preview": preview_text(_read_optional(project_dir / "storyboard.md"), 1200),
            "shot_list_preview": preview_text(_read_optional(project_dir / "shot_list.csv"), 1000),
            "captions_preview": preview_text(_read_optional(project_dir / "captions.srt"), 1000),
        },
        "signals": {
            "pipeline_status": pipeline.get("pipeline_status"),
            "rights_gate": summary.get("rights_gate") or rights_report.get("publish_gate", {}).get("gate"),
            "engagement_score": summary.get("engagement_score") or engagement.get("overall_engagement_score"),
            "monetization_status": summary.get("monetization_status") or monetization_report.get("final_recommendation", {}).get("status"),
            "production_ready": summary.get("production_ready") or production_pack.get("handoff_ready"),
            "best_monetization_routes": summary.get("best_monetization_routes", []),
            "next_actions": summary.get("next_actions", []) or ["Run final human review before production."],
        },
        "reviewer": {
            "decision": "pending",
            "decision_options": DECISION_OPTIONS,
            "checklist": [{"item": item, "passed": False, "notes": ""} for item in REVIEW_CHECKLIST],
            "reviewer_name": "",
            "review_notes": "",
            "approved_for_production": False,
            "human_review_required_before_production": True,
        },
        "files": build_file_refs(project_dir),
        "guardrails": _guardrails(),
    }


def build_file_refs(project_dir: Path) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for filename in EXPECTED_REVIEW_FILES:
        path = project_dir / filename
        refs[filename] = {
            "filename": filename,
            "path": str(path),
            "href": filename,
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "local_only": True,
        }
    return refs


def render_review_workspace_html(review: dict[str, Any], project_dir: Path) -> str:
    project = review["project"]
    creative = review["creative"]
    signals = review["signals"]
    files = review["files"]
    checklist = review["reviewer"]["checklist"]

    project_metrics = "".join([
        metric("Platform", project.get("platform")),
        metric("Audience", project.get("audience")),
        metric("Tone", project.get("tone")),
        metric("Duration", f"{project.get('duration_seconds')}s"),
        metric("Goal", project.get("monetization_goal")),
    ])
    signal_metrics = "".join([
        metric("Pipeline", signals.get("pipeline_status")),
        metric("Rights Gate", signals.get("rights_gate")),
        metric("Engagement", signals.get("engagement_score")),
        metric("Monetization", signals.get("monetization_status")),
        metric("Production Ready", signals.get("production_ready")),
    ])
    decision_html = "".join(f"<span>{esc(option)}</span>" for option in DECISION_OPTIONS)
    concept_json = json.dumps(creative.get("selected_concept"), indent=2, sort_keys=True)
    titles_html = "".join(f"<span class='pill'>{esc(title)}</span>" for title in creative.get("title_options", []))
    titles_html = titles_html or "<span class='pill'>No titles found</span>"
    next_actions_html = "".join(f"<li>{esc(item)}</li>" for item in signals.get("next_actions", []))
    checklist_html = "".join(
        f"<div class='check'><input type='checkbox'><span>{esc(item['item'])}</span></div>" for item in checklist
    )
    file_links_html = render_file_links(files)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(project.get('topic'))} — Creator Review</title>
  <style>
    :root {{ --card:#ffffff; --muted:#64748b; --line:#e2e8f0; --accent:#2563eb; --warn:#ca8a04; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f8fafc; color:#0f172a; }}
    header {{ background:linear-gradient(135deg,#0f172a,#1e293b); color:#fff; padding:34px 42px; }}
    header h1 {{ margin:0 0 10px; font-size:32px; line-height:1.1; }}
    header p {{ margin:0; color:#cbd5e1; max-width:920px; }}
    main {{ padding:28px 42px 48px; max-width:1280px; margin:0 auto; }}
    .grid {{ display:grid; grid-template-columns: repeat(12,1fr); gap:18px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:20px; box-shadow:0 10px 26px rgba(15,23,42,.06); }}
    .span-4 {{ grid-column: span 4; }} .span-6 {{ grid-column: span 6; }} .span-8 {{ grid-column: span 8; }} .span-12 {{ grid-column: span 12; }}
    h2 {{ margin:0 0 14px; font-size:20px; }} h3 {{ margin:18px 0 8px; font-size:15px; color:#334155; }}
    .metric {{ display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-bottom:1px solid #eef2f7; }}
    .metric:last-child {{ border-bottom:0; }} .label {{ color:var(--muted); }} .value {{ font-weight:700; text-align:right; }}
    .pill {{ display:inline-block; padding:6px 10px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; font-weight:700; margin:3px 4px 3px 0; }}
    pre {{ white-space:pre-wrap; background:#f1f5f9; border:1px solid #e2e8f0; padding:14px; border-radius:12px; max-height:380px; overflow:auto; line-height:1.45; }}
    a {{ color:var(--accent); text-decoration:none; font-weight:700; }} a:hover {{ text-decoration:underline; }}
    ul.clean {{ list-style:none; padding:0; margin:0; }} ul.clean li {{ padding:8px 0; border-bottom:1px solid #eef2f7; }} ul.clean li:last-child {{ border-bottom:0; }}
    .check {{ display:grid; grid-template-columns:22px 1fr; gap:10px; align-items:start; padding:8px 0; }}
    .decision {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }} .decision span {{ border:1px solid var(--line); padding:10px 12px; border-radius:12px; background:#f8fafc; font-weight:700; }}
    .notice {{ border-left:4px solid var(--warn); background:#fffbeb; padding:14px 16px; border-radius:12px; color:#713f12; }}
    .footer {{ margin-top:22px; color:var(--muted); font-size:13px; }}
    @media (max-width: 900px) {{ .span-4,.span-6,.span-8,.span-12 {{ grid-column: span 12; }} header, main {{ padding-left:22px; padding-right:22px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{esc(project.get('topic'))}</h1>
    <p>Local creator review workspace. Open this file in a browser, inspect the creative pack, then decide whether it is good enough for production, needs revision, or should be rejected.</p>
  </header>
  <main>
    <div class="grid">
      <section class="card span-4"><h2>Project</h2>{project_metrics}</section>
      <section class="card span-4"><h2>Signals</h2>{signal_metrics}</section>
      <section class="card span-4"><h2>Decision</h2><div class="decision">{decision_html}</div><p class="notice">Human approval is required before production, upload, or publishing. This workspace does not render or publish video.</p></section>
      <section class="card span-8"><h2>Creative Direction</h2><h3>Hook</h3><pre>{esc(creative.get('hook'))}</pre><h3>Selected Concept</h3><pre>{esc(concept_json)}</pre><h3>Title Options</h3><div>{titles_html}</div></section>
      <section class="card span-4"><h2>Artifact Links</h2><ul class="clean">{file_links_html}</ul></section>
      <section class="card span-6"><h2>Script Preview</h2><pre>{esc(creative.get('script_preview'))}</pre></section>
      <section class="card span-6"><h2>Storyboard Preview</h2><pre>{esc(creative.get('storyboard_preview'))}</pre></section>
      <section class="card span-6"><h2>Shot List Preview</h2><pre>{esc(creative.get('shot_list_preview'))}</pre></section>
      <section class="card span-6"><h2>Captions Preview</h2><pre>{esc(creative.get('captions_preview'))}</pre></section>
      <section class="card span-6"><h2>Next Actions</h2><ul>{next_actions_html}</ul></section>
      <section class="card span-6"><h2>Review Checklist</h2>{checklist_html}</section>
      <section class="card span-12"><h2>Reviewer Notes</h2><p class="notice">Static HTML cannot save notes by itself. Use this section while reviewing, then copy your notes into your project tracker or update the JSON manually if needed.</p><pre>Reviewer:\nDecision: pending\nNotes:</pre></section>
    </div>
    <p class="footer">Generated locally in {esc(str(project_dir))}. No cloud deployment, upload, platform API call, or rendering was performed.</p>
  </main>
</body>
</html>
"""


def render_file_links(files: dict[str, dict[str, Any]]) -> str:
    rows = []
    for name, data in files.items():
        if data.get("exists"):
            rows.append(f'<li><a href="{esc(data["href"])}">{esc(name)}</a> <span class="label">({data.get("bytes", 0)} bytes)</span></li>')
        else:
            rows.append(f'<li><span class="label">Missing: {esc(name)}</span></li>')
    return "".join(rows)


def metric(label: str, value: Any) -> str:
    return f'<div class="metric"><span class="label">{esc(label)}</span><span class="value">{esc(value)}</span></div>'


def first_item(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value or {}


def preview_text(value: Any, max_chars: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n..."


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _assert_within_root(root: Path, target: Path) -> None:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Target path escapes output root: {target}") from exc


def _invalid(errors: list[str], *, export_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": P54_WORKSPACE_VERSION,
        "is_valid": False,
        "validation_errors": errors,
        **_guardrails(),
    }
    if export_pack is not None:
        payload["export_pack"] = export_pack
    return payload


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
        "monetization_guaranteed": False,
        "performance_guaranteed": False,
        "human_review_required_before_production": True,
    }


def _cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "output_dir": result.get("output_dir"),
        "index_html_path": result.get("index_html_path"),
        "creator_review_path": result.get("creator_review_path"),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a local creator review workspace.")
    parser.add_argument("brief_json", help="Path to local video brief JSON file.")
    parser.add_argument("--output-root", default="outputs/review-demo", help="Local output root.")
    parser.add_argument("--project-slug", default=None, help="Optional local folder slug.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing local folder.")
    args = parser.parse_args(argv)
    try:
        result = build_creator_review_workspace(
            args.brief_json,
            args.output_root,
            project_slug=args.project_slug,
            overwrite=args.overwrite,
        )
        print(_json_dump(_cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover - CLI safety contract.
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
