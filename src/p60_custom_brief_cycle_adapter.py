"""P60 custom brief review cycle adapter.

This module bridges a single Creator Studio brief into the local review cycle by
writing a one-item P55/P58-compatible brief library and a matching reviewer
feedback template. It does not run external services, render video, upload,
publish, or automate final production approval.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

P60_ADAPTER_VERSION = "p60.custom_brief_review_cycle_adapter.v1"
LIBRARY_FILENAME = "custom_brief_library.json"
FEEDBACK_FILENAME = "custom_feedback_template.json"
MANIFEST_FILENAME = "custom_cycle_manifest.json"
README_FILENAME = "custom_cycle_readme.md"
DEFAULT_OUTPUT_ROOT = "outputs/custom-brief-cycle"
DEFAULT_REVIEW_OUTPUT = "outputs/custom-review-cycle"

REQUIRED_FIELDS = ("topic", "platform", "audience")


def load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object.")
    return data


def adapt_custom_brief(
    brief_source: dict[str, Any] | str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write custom brief cycle adapter files for one brief."""

    normalized = normalize_brief_source(brief_source)
    root = Path(output_root).expanduser().resolve()
    if not normalized.get("is_valid"):
        return {
            "schema_version": P60_ADAPTER_VERSION,
            "is_valid": False,
            "output_root": str(root),
            "validation_errors": normalized.get("validation_errors", []),
            **guardrails(),
        }

    root.mkdir(parents=True, exist_ok=True)
    brief = normalized["brief"]
    demo_slug = demo_slug_for(brief)
    library = build_custom_library(brief, demo_slug)
    feedback = build_feedback_template(brief, demo_slug)
    p58 = p58_command(root / LIBRARY_FILENAME, root / FEEDBACK_FILENAME, DEFAULT_REVIEW_OUTPUT)

    outputs = {
        LIBRARY_FILENAME: json_dump(library),
        FEEDBACK_FILENAME: json_dump(feedback),
        README_FILENAME: render_readme(brief, demo_slug, p58),
    }
    written: list[dict[str, Any]] = []
    for filename, content in outputs.items():
        path = root / filename
        write_file(path, content, overwrite=overwrite)
        written.append(file_view(root, path, content))

    manifest = build_manifest(root, demo_slug, written, p58)
    manifest_path = root / MANIFEST_FILENAME
    manifest_content = json_dump(manifest)
    write_file(manifest_path, manifest_content, overwrite=overwrite)
    written.append(file_view(root, manifest_path, manifest_content))

    return {
        "schema_version": P60_ADAPTER_VERSION,
        "is_valid": True,
        "output_root": str(root),
        "demo_slug": demo_slug,
        "custom_brief_library_path": str(root / LIBRARY_FILENAME),
        "custom_feedback_template_path": str(root / FEEDBACK_FILENAME),
        "custom_cycle_manifest_path": str(manifest_path),
        "custom_cycle_readme_path": str(root / README_FILENAME),
        "p58_command": p58,
        "expected_review_cycle_index": str(Path(DEFAULT_REVIEW_OUTPUT).expanduser().resolve() / "review_cycle_index.html"),
        "written_files": written,
        **guardrails(),
    }


def normalize_brief_source(brief_source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Load and normalize a single brief object."""

    try:
        data = load_json(brief_source) if isinstance(brief_source, (str, Path)) else brief_source
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"is_valid": False, "validation_errors": [str(exc)]}
    if not isinstance(data, dict):
        return {"is_valid": False, "validation_errors": ["brief_must_be_object"]}
    if isinstance(data.get("brief"), dict):
        data = data["brief"]
    if isinstance(data.get("briefs"), list):
        briefs = [item for item in data["briefs"] if isinstance(item, dict)]
        if len(briefs) != 1:
            return {"is_valid": False, "validation_errors": ["brief_library_must_contain_exactly_one_brief"]}
        data = briefs[0]

    errors = [f"missing_{field}" for field in REQUIRED_FIELDS if not str(data.get(field) or "").strip()]
    if errors:
        return {"is_valid": False, "validation_errors": errors}
    return {"is_valid": True, "brief": normalize_single_brief(data)}


def normalize_single_brief(data: dict[str, Any]) -> dict[str, Any]:
    """Return a P55/P58-compatible single brief."""

    topic = str(data.get("topic") or "Custom video brief").strip()
    demo_id = str(data.get("demo_id") or slugify(topic)).strip()
    return {
        "demo_id": slugify(demo_id) or slugify(topic),
        "topic": topic,
        "platform": str(data.get("platform") or "youtube_shorts").strip(),
        "audience": str(data.get("audience") or "target audience").strip(),
        "tone": str(data.get("tone") or "clear, practical, engaging").strip(),
        "duration_seconds": normalize_duration(data.get("duration_seconds")),
        "content_format": str(data.get("content_format") or infer_format(str(data.get("platform") or ""))).strip(),
        "monetization_goal": str(data.get("monetization_goal") or "generate qualified interest").strip(),
        "must_use_points": as_list(data.get("must_use_points")),
        "avoid": as_list(data.get("avoid")),
        "source_notes": as_list(data.get("source_notes")),
    }


def build_custom_library(brief: dict[str, Any], demo_slug: str) -> dict[str, Any]:
    custom = dict(brief)
    custom["demo_id"] = demo_slug
    return {
        "schema_version": "p60.custom_brief_library.v1",
        "adapter_version": P60_ADAPTER_VERSION,
        "brief_count": 1,
        "briefs": [custom],
        "local_only": True,
        "human_review_required_before_production": True,
    }


def build_feedback_template(brief: dict[str, Any], demo_slug: str) -> dict[str, Any]:
    return {
        "schema_version": "p60.custom_feedback_template.v1",
        "reviewer_name": "Human Reviewer",
        "review_round": "custom_brief_review_1",
        "instructions": "Run the custom brief review cycle, inspect the generated workspace, then update decision, score, strengths, issues, requested_changes, and approval_notes before final selection.",
        "reviews": [
            {
                "demo_slug": demo_slug,
                "decision": "revise",
                "score": 70,
                "strengths": ["Custom brief is ready for first-pass review."],
                "issues": ["Replace these placeholder notes after reviewing the generated content pack."],
                "requested_changes": ["Update this with real reviewer feedback after opening the review workspace."],
                "approval_notes": f"Review custom brief for {brief.get('platform')} before any production use.",
            }
        ],
    }


def build_manifest(root: Path, demo_slug: str, written: list[dict[str, Any]], command: str) -> dict[str, Any]:
    return {
        "schema_version": P60_ADAPTER_VERSION,
        "output_root": str(root),
        "demo_slug": demo_slug,
        "files": written,
        "p58_command": command,
        "next_steps": [
            "Open custom_cycle_readme.md and confirm the generated brief library.",
            "Run the P58 command shown in the readme to generate the local review cycle.",
            "Open the resulting review_cycle_index.html and review outputs manually.",
            "Edit custom_feedback_template.json with real feedback before final revision decisions.",
        ],
        **guardrails(),
    }


def render_readme(brief: dict[str, Any], demo_slug: str, command: str) -> str:
    return "\n".join([
        "# Custom Brief Review Cycle Adapter",
        "",
        f"Demo slug: `{demo_slug}`",
        f"Topic: {brief.get('topic')}",
        f"Platform: {brief.get('platform')}",
        "",
        "## Generated files",
        f"- `{LIBRARY_FILENAME}` — one-item brief library compatible with P55/P58",
        f"- `{FEEDBACK_FILENAME}` — matching reviewer feedback template",
        f"- `{MANIFEST_FILENAME}` — local artifact map",
        f"- `{README_FILENAME}` — this operator guide",
        "",
        "## Run the local review cycle",
        "",
        "```bash",
        command,
        "```",
        "",
        "Then open:",
        "",
        f"`{DEFAULT_REVIEW_OUTPUT}/review_cycle_index.html`",
        "",
        "## Important review note",
        "",
        "The generated feedback template contains placeholder review notes. Use it for smoke testing, then update it with real human feedback after opening the generated content pack.",
        "",
        "## Guardrails",
        "",
        "This adapter is local-only. It does not render, upload, publish, call external services, or approve content for production automatically. Human review is required before production.",
        "",
    ])


def write_file(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_text(content, encoding="utf-8")


def file_view(root: Path, path: Path, content: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "relative_path": relative_href(root, path),
        "bytes": len(content.encode("utf-8")),
    }


def p58_command(brief_library: str | Path, feedback_template: str | Path, output_root: str | Path) -> str:
    return " ".join([
        "python -m src.p58_review_cycle_runner",
        f"--demo-briefs {brief_library}",
        f"--feedback {feedback_template}",
        f"--output-root {output_root}",
        "--overwrite",
    ])


def demo_slug_for(brief: dict[str, Any]) -> str:
    raw = str(brief.get("demo_id") or brief.get("topic") or "custom-brief")
    return slugify(raw)[:70] or "custom-brief"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def infer_format(platform: str) -> str:
    platform = platform.lower()
    if "long" in platform:
        return "longform_video"
    if "carousel" in platform:
        return "carousel_newsletter"
    return "vertical_short"


def normalize_duration(value: Any) -> int:
    try:
        duration = int(float(value))
    except (TypeError, ValueError):
        duration = 45
    return max(15, min(1800, duration))


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip(" -") for item in re.split(r"[\n;]+", text) if item.strip(" -")]


def relative_href(root: Path, target: Path | str) -> str:
    target_path = Path(target)
    try:
        return target_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return target_path.name


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
        "demo_slug": result.get("demo_slug"),
        "custom_brief_library_path": result.get("custom_brief_library_path"),
        "custom_feedback_template_path": result.get("custom_feedback_template_path"),
        "p58_command": result.get("p58_command"),
        "local_only": result.get("local_only", True),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapt one local brief into custom review-cycle inputs.")
    parser.add_argument("brief_json", help="Path to a single Creator Studio brief JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Local adapter output root.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing adapter files.")
    args = parser.parse_args(argv)
    try:
        result = adapt_custom_brief(args.brief_json, args.output_root, overwrite=args.overwrite)
        print(json_dump(cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover
        print(json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
