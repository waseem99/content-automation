"""P59 local Creator Studio starter.

This module creates a browser-openable local workspace that helps a human draft
video content briefs and then run the existing P58 one-command local review
cycle. The HTML page is static and local-only: it does not call a server, deploy,
render video, upload, publish, track, or call external services.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

P59_STUDIO_VERSION = "p59.local_creator_studio_starter.v1"
STUDIO_HTML = "creator_studio.html"
SAMPLE_BRIEF = "sample_brief.json"
STUDIO_MANIFEST = "studio_manifest.json"
STUDIO_README = "studio_readme.md"
DEFAULT_OUTPUT_ROOT = "outputs/creator-studio"


def default_sample_brief() -> dict[str, Any]:
    """Return a realistic starter brief for the local studio."""

    return {
        "demo_id": "custom-ai-operations-short",
        "topic": "AI operations audit for service businesses",
        "platform": "youtube_shorts",
        "audience": "agency founders and service business owners with manual operations",
        "tone": "practical, confident, high-trust, founder-led",
        "duration_seconds": 45,
        "content_format": "vertical_short",
        "monetization_goal": "generate qualified leads for a paid AI operations audit",
        "must_use_points": [
            "Open with the hidden cost of manual follow-ups and scattered tools.",
            "Show a simple before/after workflow from lead capture to follow-up.",
            "End with a soft CTA to request an operations audit checklist.",
        ],
        "avoid": [
            "Do not promise guaranteed revenue, savings, or automation success.",
            "Do not use celebrity likeness, copied music, third-party clips, or brand logos.",
        ],
        "source_notes": [
            "Use original narration, owned diagrams, simple UI mockups, and licensed or owned assets only."
        ],
    }


def build_studio_workspace(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    sample_brief: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write the local Creator Studio starter workspace."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    brief = sample_brief or default_sample_brief()
    files = {
        STUDIO_HTML: render_studio_html(brief),
        SAMPLE_BRIEF: json_dump(brief),
        STUDIO_README: render_studio_readme(root),
    }
    written: list[dict[str, Any]] = []
    for filename, content in files.items():
        path = root / filename
        if path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")
        path.write_text(content, encoding="utf-8")
        written.append(file_view(root, path, content))

    manifest = build_manifest(root, written)
    manifest_path = root / STUDIO_MANIFEST
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {manifest_path}")
    manifest_path.write_text(json_dump(manifest), encoding="utf-8")
    written.append(file_view(root, manifest_path, json_dump(manifest)))

    return {
        "schema_version": P59_STUDIO_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "creator_studio_html_path": str(root / STUDIO_HTML),
        "sample_brief_path": str(root / SAMPLE_BRIEF),
        "studio_manifest_path": str(manifest_path),
        "studio_readme_path": str(root / STUDIO_README),
        "p58_command": p58_command(str(root / SAMPLE_BRIEF), "outputs/review-cycle-custom"),
        "written_files": written,
        **guardrails(),
    }


def build_manifest(root: Path, written: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": P59_STUDIO_VERSION,
        "output_root": str(root),
        "files": written,
        "open_first": STUDIO_HTML,
        "sample_brief": SAMPLE_BRIEF,
        "p58_command": p58_command(str(root / SAMPLE_BRIEF), "outputs/review-cycle-custom"),
        "usage_steps": [
            "Open creator_studio.html in a browser.",
            "Draft or edit the content brief.",
            "Copy or download the generated JSON as a local brief file.",
            "Run the P58 local review cycle command from a terminal.",
            "Open the generated review_cycle_index.html for review.",
        ],
        **guardrails(),
    }


def render_studio_html(brief: dict[str, Any]) -> str:
    brief_json = json.dumps(brief, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Local Creator Studio Starter</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #0f172a; }}
    header {{ padding: 34px 42px; background: linear-gradient(135deg, #111827, #1d4ed8); color: white; }}
    header h1 {{ margin: 0 0 8px; font-size: 32px; }}
    header p {{ margin: 0; color: #dbeafe; max-width: 980px; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 28px 36px 52px; }}
    .layout {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .panel {{ background: white; border: 1px solid #e2e8f0; border-radius: 18px; padding: 20px; box-shadow: 0 10px 26px rgba(15, 23, 42, .06); }}
    label {{ display: block; font-size: 13px; font-weight: 800; color: #334155; margin: 12px 0 6px; }}
    input, textarea, select {{ width: 100%; border: 1px solid #cbd5e1; border-radius: 12px; padding: 11px 12px; font: inherit; color: #0f172a; background: #ffffff; }}
    textarea {{ min-height: 86px; resize: vertical; }}
    pre {{ white-space: pre-wrap; background: #0f172a; color: #dbeafe; padding: 16px; border-radius: 14px; overflow: auto; min-height: 360px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    button {{ border: 0; border-radius: 12px; padding: 11px 14px; font-weight: 800; cursor: pointer; background: #2563eb; color: white; }}
    button.secondary {{ background: #0f172a; }}
    .notice {{ margin-top: 18px; border-left: 4px solid #ca8a04; background: #fffbeb; padding: 14px 16px; border-radius: 12px; color: #713f12; }}
    code {{ background: #e2e8f0; padding: 2px 5px; border-radius: 6px; }}
    @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} header, main {{ padding-left: 20px; padding-right: 20px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Local Creator Studio Starter</h1>
    <p>Draft a video content brief locally, copy or download the JSON, then run the local review cycle. No upload, tracking, hosted app, or external network call is used.</p>
  </header>
  <main>
    <section class=\"layout\">
      <form class=\"panel\" id=\"brief-form\">
        <label for=\"demo_id\">Demo ID</label>
        <input id=\"demo_id\" value=\"{esc_attr(brief.get('demo_id'))}\">
        <label for=\"topic\">Topic</label>
        <input id=\"topic\" value=\"{esc_attr(brief.get('topic'))}\">
        <label for=\"platform\">Platform</label>
        <select id=\"platform\">
          {option('youtube_shorts', brief.get('platform'))}
          {option('instagram_reels', brief.get('platform'))}
          {option('tiktok', brief.get('platform'))}
          {option('youtube_long', brief.get('platform'))}
          {option('linkedin_video', brief.get('platform'))}
        </select>
        <label for=\"audience\">Audience</label>
        <textarea id=\"audience\">{esc_text(brief.get('audience'))}</textarea>
        <label for=\"tone\">Tone</label>
        <input id=\"tone\" value=\"{esc_attr(brief.get('tone'))}\">
        <label for=\"duration_seconds\">Duration seconds</label>
        <input id=\"duration_seconds\" type=\"number\" min=\"15\" max=\"900\" value=\"{int(brief.get('duration_seconds', 45))}\">
        <label for=\"content_format\">Content format</label>
        <input id=\"content_format\" value=\"{esc_attr(brief.get('content_format'))}\">
        <label for=\"monetization_goal\">Monetization goal</label>
        <textarea id=\"monetization_goal\">{esc_text(brief.get('monetization_goal'))}</textarea>
        <label for=\"must_use_points\">Must-use points, one per line</label>
        <textarea id=\"must_use_points\">{esc_text(lines(brief.get('must_use_points')))}</textarea>
        <label for=\"avoid\">Avoid / safety notes, one per line</label>
        <textarea id=\"avoid\">{esc_text(lines(brief.get('avoid')))}</textarea>
        <label for=\"source_notes\">Source / asset notes, one per line</label>
        <textarea id=\"source_notes\">{esc_text(lines(brief.get('source_notes')))}</textarea>
      </form>
      <section class=\"panel\">
        <h2>Generated brief JSON</h2>
        <pre id=\"json-output\">{esc_text(brief_json)}</pre>
        <div class=\"actions\">
          <button type=\"button\" onclick=\"copyJson()\">Copy JSON</button>
          <button type=\"button\" class=\"secondary\" onclick=\"downloadJson()\">Download brief.json</button>
        </div>
        <div class=\"notice\">
          Save the JSON locally, then run:<br><br>
          <code>python -m src.p58_review_cycle_runner --demo-briefs path/to/brief.json --feedback docs/operations/p56-review-feedback-template.json --output-root outputs/review-cycle-custom --overwrite</code><br><br>
          Then open <code>outputs/review-cycle-custom/review_cycle_index.html</code>.
        </div>
      </section>
    </section>
  </main>
  <script>
    const fields = ['demo_id','topic','platform','audience','tone','duration_seconds','content_format','monetization_goal','must_use_points','avoid','source_notes'];
    function listValue(id) {{ return document.getElementById(id).value.split('\n').map(x => x.trim()).filter(Boolean); }}
    function buildBrief() {{
      return {{
        demo_id: document.getElementById('demo_id').value.trim(),
        topic: document.getElementById('topic').value.trim(),
        platform: document.getElementById('platform').value.trim(),
        audience: document.getElementById('audience').value.trim(),
        tone: document.getElementById('tone').value.trim(),
        duration_seconds: Number(document.getElementById('duration_seconds').value || 45),
        content_format: document.getElementById('content_format').value.trim(),
        monetization_goal: document.getElementById('monetization_goal').value.trim(),
        must_use_points: listValue('must_use_points'),
        avoid: listValue('avoid'),
        source_notes: listValue('source_notes')
      }};
    }}
    function refreshJson() {{ document.getElementById('json-output').textContent = JSON.stringify(buildBrief(), null, 2); }}
    function copyJson() {{ navigator.clipboard.writeText(document.getElementById('json-output').textContent); }}
    function downloadJson() {{
      const blob = new Blob([document.getElementById('json-output').textContent + '\n'], {{ type: 'application/json' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (document.getElementById('demo_id').value.trim() || 'brief') + '.json';
      a.click();
      URL.revokeObjectURL(a.href);
    }}
    fields.forEach(id => document.getElementById(id).addEventListener('input', refreshJson));
    refreshJson();
  </script>
</body>
</html>
"""


def render_studio_readme(root: Path) -> str:
    return f"""# Local Creator Studio Starter

Open `creator_studio.html` in your browser and draft a video content brief.

## Local workflow

1. Open `creator_studio.html`.
2. Fill the brief fields.
3. Copy or download the generated JSON.
4. Save it as a local file, for example `custom_brief.json`.
5. Run the local review cycle:

```bash
python -m src.p58_review_cycle_runner \
  --demo-briefs custom_brief.json \
  --feedback docs/operations/p56-review-feedback-template.json \
  --output-root outputs/review-cycle-custom \
  --overwrite
```

Then open:

```text
outputs/review-cycle-custom/review_cycle_index.html
```

## Files in this workspace

- `creator_studio.html` — static local brief builder
- `sample_brief.json` — starter brief
- `studio_manifest.json` — generated file map
- `studio_readme.md` — this guide

## Guardrails

This is local-only. It does not deploy, host an app, render videos, download assets, upload, publish, track analytics, call external services, or approve content for production automatically.

Human review is required before production.

Workspace root: `{root}`
"""


def p58_command(brief_path: str, output_root: str) -> str:
    return (
        "python -m src.p58_review_cycle_runner "
        f"--demo-briefs {brief_path} "
        "--feedback docs/operations/p56-review-feedback-template.json "
        f"--output-root {output_root} --overwrite"
    )


def file_view(root: Path, path: Path, content: str) -> dict[str, Any]:
    return {
        "filename": path.name,
        "path": str(path),
        "href": relative_href(root, path),
        "bytes": len(content.encode("utf-8")),
        "local_only": True,
    }


def option(value: str, current: Any) -> str:
    selected = " selected" if str(current) == value else ""
    return f'<option value="{html.escape(value)}"{selected}>{html.escape(value)}</option>'


def lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")


def relative_href(root: Path, target: Path) -> str:
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return target.name


def esc_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def esc_attr(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


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
        "creator_studio_html_path": result.get("creator_studio_html_path"),
        "sample_brief_path": result.get("sample_brief_path"),
        "studio_manifest_path": result.get("studio_manifest_path"),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a local Creator Studio starter workspace.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Local output root for the studio workspace.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing studio files.")
    args = parser.parse_args(argv)
    try:
        result = build_studio_workspace(args.output_root, overwrite=args.overwrite)
        print(json_dump(cli_summary(result)), end="")
        return 0
    except Exception as exc:  # pragma: no cover
        print(json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
