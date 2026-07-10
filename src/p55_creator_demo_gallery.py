"""P55 local creator demo gallery.

This module generates multiple P54 local creator review workspaces and combines
those review workspaces into one browser-openable local gallery. It exists so a
human can review several generated content packs side by side before production,
rendering, deployment, upload, or publishing.

It does not deploy, host a UI/API, render video, download assets, upload,
publish, call external services, or guarantee monetization/performance.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from src.p54_creator_review_workspace import build_creator_review_workspace

P55_GALLERY_VERSION = "p55.local_creator_demo_gallery.v1"
DEMO_GALLERY_FILENAME = "demo_gallery.json"
GALLERY_INDEX_FILENAME = "index.html"


def load_demo_briefs(source: list[dict[str, Any]] | dict[str, Any] | str | Path) -> list[dict[str, Any]]:
    """Load demo briefs from a list, object with `briefs`, or JSON path."""

    if isinstance(source, (str, Path)):
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        data = source
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    if isinstance(data, dict) and isinstance(data.get("briefs"), list):
        briefs = data["briefs"]
        if all(isinstance(item, dict) for item in briefs):
            return briefs
    raise ValueError("Demo briefs must be a list of objects or an object with a briefs list.")


def build_creator_demo_gallery(
    brief_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    output_root: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate one P54 workspace per brief plus gallery HTML/JSON."""

    try:
        briefs = load_demo_briefs(brief_source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _invalid([str(exc)])
    if not briefs:
        return _invalid(["missing_demo_briefs"])

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    demos: list[dict[str, Any]] = []
    for index, brief in enumerate(briefs, start=1):
        slug = demo_slug(brief, index)
        workspace = build_creator_review_workspace(
            brief,
            root,
            project_slug=slug,
            overwrite=overwrite,
        )
        demos.append(build_demo_entry(index, brief, slug, workspace, root))

    gallery = build_gallery_summary(demos, root)
    gallery_path = root / DEMO_GALLERY_FILENAME
    index_path = root / GALLERY_INDEX_FILENAME
    gallery_path.write_text(_json_dump(gallery), encoding="utf-8")
    index_path.write_text(render_gallery_html(gallery), encoding="utf-8")

    return {
        "schema_version": P55_GALLERY_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "gallery_index_path": str(index_path),
        "demo_gallery_path": str(gallery_path),
        "demo_count": len(demos),
        "successful_demo_count": sum(1 for item in demos if item["is_valid"]),
        "demos": demos,
        **_guardrails(),
    }


def build_demo_entry(index: int, brief: dict[str, Any], slug: str, workspace: dict[str, Any], root: Path) -> dict[str, Any]:
    output_dir = Path(workspace.get("output_dir", root / slug)).resolve()
    review = read_creator_review(output_dir)
    signals = review.get("signals", {}) if isinstance(review, dict) else {}
    project = review.get("project", {}) if isinstance(review, dict) else {}
    index_path = Path(workspace.get("index_html_path", output_dir / "index.html")).resolve()
    review_path = Path(workspace.get("creator_review_path", output_dir / "creator_review.json")).resolve()
    return {
        "demo_number": index,
        "demo_slug": slug,
        "is_valid": bool(workspace.get("is_valid")),
        "topic": project.get("topic") or brief.get("topic"),
        "platform": project.get("platform") or brief.get("platform"),
        "audience": project.get("audience") or brief.get("audience"),
        "monetization_goal": project.get("monetization_goal") or brief.get("monetization_goal"),
        "workspace_dir": str(output_dir),
        "workspace_index_path": str(index_path),
        "workspace_index_href": _relative_href(root, index_path),
        "creator_review_path": str(review_path),
        "creator_review_href": _relative_href(root, review_path),
        "pipeline_status": signals.get("pipeline_status"),
        "rights_gate": signals.get("rights_gate"),
        "engagement_score": signals.get("engagement_score"),
        "monetization_status": signals.get("monetization_status"),
        "production_ready": signals.get("production_ready"),
        "next_actions": signals.get("next_actions", []) if isinstance(signals.get("next_actions", []), list) else [],
        "validation_errors": workspace.get("validation_errors", []),
        "human_review_required_before_production": True,
        "local_only": True,
    }


def build_gallery_summary(demos: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    return {
        "schema_version": P55_GALLERY_VERSION,
        "output_root": str(root),
        "demo_count": len(demos),
        "successful_demo_count": sum(1 for item in demos if item["is_valid"]),
        "ready_for_review_count": sum(1 for item in demos if item.get("workspace_index_href") and item["is_valid"]),
        "demos": demos,
        "review_guidance": {
            "primary_question": "Which generated content pack is strongest enough to move toward production?",
            "review_decisions": ["approve_for_production", "revise", "reject"],
            "human_review_required_before_production": True,
        },
        **_guardrails(),
    }


def render_gallery_html(gallery: dict[str, Any]) -> str:
    cards = "".join(render_demo_card(item) for item in gallery.get("demos", []))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Creator Demo Gallery</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #0f172a; }}
    header {{ padding: 38px 44px; background: linear-gradient(135deg, #0f172a, #1d4ed8); color: white; }}
    header h1 {{ margin: 0 0 10px; font-size: 34px; }}
    header p {{ margin: 0; color: #dbeafe; max-width: 980px; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px 42px 48px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }}
    .metric {{ background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.06); }}
    .metric span {{ display: block; color: #64748b; font-size: 13px; }}
    .metric strong {{ display: block; font-size: 30px; margin-top: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 18px; padding: 20px; box-shadow: 0 10px 26px rgba(15,23,42,.06); }}
    .card h2 {{ margin: 0 0 10px; font-size: 22px; line-height: 1.2; }}
    .muted {{ color: #64748b; }}
    .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; font-weight: 700; margin: 3px 4px 8px 0; }}
    .signals {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 12px 0; }}
    .signal {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; }}
    .signal span {{ display: block; color: #64748b; font-size: 12px; }}
    .signal strong {{ display: block; margin-top: 4px; font-size: 14px; }}
    a.button {{ display: inline-block; margin-top: 12px; padding: 11px 14px; border-radius: 12px; background: #2563eb; color: white; font-weight: 800; text-decoration: none; }}
    ul {{ padding-left: 18px; }}
    .notice {{ margin-top: 22px; border-left: 4px solid #ca8a04; background: #fffbeb; padding: 14px 16px; border-radius: 12px; color: #713f12; }}
    @media (max-width: 900px) {{ .summary, .grid {{ grid-template-columns: 1fr; }} header, main {{ padding-left: 22px; padding-right: 22px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Creator Demo Gallery</h1>
    <p>Local review gallery for generated content packs. Open each review workspace, inspect the hook, script, storyboard, rights notes, monetization signals, and decide whether it is production-worthy.</p>
  </header>
  <main>
    <section class=\"summary\">
      <div class=\"metric\"><span>Total demos</span><strong>{int(gallery.get('demo_count', 0))}</strong></div>
      <div class=\"metric\"><span>Generated</span><strong>{int(gallery.get('successful_demo_count', 0))}</strong></div>
      <div class=\"metric\"><span>Ready to review</span><strong>{int(gallery.get('ready_for_review_count', 0))}</strong></div>
    </section>
    <section class=\"grid\">{cards}</section>
    <p class=\"notice\">This is local review only. No video rendering, uploading, publishing, platform API call, hosted UI, tracking, or performance guarantee is included.</p>
  </main>
</body>
</html>
"""


def render_demo_card(item: dict[str, Any]) -> str:
    next_actions = item.get("next_actions", []) or ["Open the workspace and complete human review."]
    actions = "".join(f"<li>{esc(action)}</li>" for action in next_actions[:4])
    href = item.get("workspace_index_href", "")
    button = f"<a class=\"button\" href=\"{esc(href)}\">Open review workspace</a>" if href else "<p class=\"muted\">Workspace unavailable</p>"
    return f"""
      <article class=\"card\">
        <span class=\"pill\">Demo {int(item.get('demo_number', 0))}</span>
        <span class=\"pill\">{esc(item.get('platform'))}</span>
        <h2>{esc(item.get('topic'))}</h2>
        <p class=\"muted\"><strong>Audience:</strong> {esc(item.get('audience'))}</p>
        <p class=\"muted\"><strong>Goal:</strong> {esc(item.get('monetization_goal'))}</p>
        <div class=\"signals\">
          {signal('Pipeline', item.get('pipeline_status'))}
          {signal('Rights', item.get('rights_gate'))}
          {signal('Engagement', item.get('engagement_score'))}
          {signal('Monetization', item.get('monetization_status'))}
        </div>
        <h3>Next actions</h3>
        <ul>{actions}</ul>
        {button}
      </article>
    """


def signal(label: str, value: Any) -> str:
    return f"<div class=\"signal\"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>"


def demo_slug(brief: dict[str, Any], index: int) -> str:
    raw = str(brief.get("demo_id") or brief.get("topic") or f"demo-{index}").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:70] or f"demo-{index}"


def read_creator_review(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "creator_review.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a local creator demo gallery.")
    parser.add_argument("briefs_json", help="Path to JSON file with a briefs list.")
    parser.add_argument("--output-root", default="outputs/demo-gallery", help="Local gallery output root.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing demo folders.")
    args = parser.parse_args(argv)
    result = build_creator_demo_gallery(args.briefs_json, args.output_root, overwrite=args.overwrite)
    print(_json_dump(_cli_summary(result)), end="")
    return 0 if result.get("is_valid") else 2


def _relative_href(root: Path, target: Path) -> str:
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return target.name


def _invalid(errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": P55_GALLERY_VERSION,
        "is_valid": False,
        "validation_errors": errors,
        **_guardrails(),
    }


def _cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "gallery_index_path": result.get("gallery_index_path"),
        "demo_count": result.get("demo_count", 0),
        "successful_demo_count": result.get("successful_demo_count", 0),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
