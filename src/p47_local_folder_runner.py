"""P47 local CLI and folder export runner.

This module writes the P46 producer export pack to a local project folder. It is
intended for producers and editors who need files on disk without deploying a UI,
API, worker, cloud service, renderer, uploader, or external integration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from src.p46_local_export_pack import build_local_export_pack

P47_RUNNER_VERSION = "p47.local_folder_runner.v1"


def load_brief_json(path: str | Path) -> dict[str, Any]:
    """Load a local JSON brief file."""

    brief_path = Path(path)
    data = json.loads(brief_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Brief JSON must be an object.")
    return data


def slugify_project_name(payload: dict[str, Any], fallback: str = "video-project") -> str:
    """Create a deterministic folder slug from topic and platform."""

    brief = payload.get("brief", payload) if isinstance(payload, dict) else {}
    topic = str(brief.get("topic") or brief.get("niche") or fallback)
    platform = str(brief.get("platform") or "local")
    raw = f"{topic}-{platform}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:80] or fallback


def run_local_folder_export(
    payload: dict[str, Any],
    output_root: str | Path,
    *,
    project_slug: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a P46 export pack and write it to a local project folder."""

    export_pack = build_local_export_pack(payload)
    if not export_pack.get("is_valid"):
        return {
            "schema_version": P47_RUNNER_VERSION,
            "is_valid": False,
            "validation_errors": export_pack.get("validation_errors", []),
            "export_pack": export_pack,
            **_guardrails(),
        }
    root = Path(output_root).expanduser().resolve()
    slug = slugify_project_name(payload if project_slug is None else {"topic": project_slug})
    project_dir = (root / slug).resolve()
    _assert_within_root(root, project_dir)
    if project_dir.exists() and any(project_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Output folder already exists and is not empty: {project_dir}")
    project_dir.mkdir(parents=True, exist_ok=True)
    files = dict(export_pack["files"])
    summary = build_summary(export_pack, project_dir)
    manifest = build_write_manifest(files, project_dir)
    files["manifest.json"] = _json_dump(manifest)
    files["summary.json"] = _json_dump(summary)
    written_files = _write_files(project_dir, files)
    summary["written_files"] = written_files
    summary["file_count"] = len(written_files)
    (project_dir / "summary.json").write_text(_json_dump(summary), encoding="utf-8")
    manifest = build_write_manifest(files, project_dir)
    (project_dir / "manifest.json").write_text(_json_dump(manifest), encoding="utf-8")
    return {
        "schema_version": P47_RUNNER_VERSION,
        "is_valid": True,
        "output_dir": str(project_dir),
        "project_slug": slug,
        "file_count": len(written_files),
        "written_files": written_files,
        "summary": summary,
        "manifest": manifest,
        **_guardrails(),
    }


def build_summary(export_pack: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Create a local run summary for producers."""

    pipeline = export_pack.get("pipeline_package", {})
    summary = pipeline.get("summary", {})
    video = pipeline.get("video_package", {})
    brief = video.get("brief", {}) if isinstance(video, dict) else {}
    return {
        "schema_version": "p47.local_export_summary.v1",
        "output_dir": str(output_dir),
        "topic": brief.get("topic"),
        "platform": brief.get("platform"),
        "pipeline_status": pipeline.get("pipeline_status"),
        "rights_gate": summary.get("rights_gate"),
        "engagement_score": summary.get("engagement_score"),
        "monetization_status": summary.get("monetization_status"),
        "production_ready": summary.get("production_ready"),
        "next_actions": summary.get("next_actions", []),
        **_guardrails(),
    }


def build_write_manifest(files: dict[str, str], output_dir: Path) -> list[dict[str, Any]]:
    """Build a manifest for files written to disk."""

    return [
        {
            "filename": name,
            "path": str(output_dir / name),
            "content_type": _content_type(name),
            "bytes": len(content.encode("utf-8")),
            "local_only": True,
        }
        for name, content in sorted(files.items())
    ]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for local folder export."""

    parser = argparse.ArgumentParser(description="Generate a local video export folder.")
    parser.add_argument("brief_json", help="Path to local brief JSON file.")
    parser.add_argument("--output-root", default="outputs", help="Local output root.")
    parser.add_argument("--project-slug", default=None, help="Optional folder slug.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing folder.")
    args = parser.parse_args(argv)
    try:
        brief = load_brief_json(args.brief_json)
        result = run_local_folder_export(
            brief,
            args.output_root,
            project_slug=args.project_slug,
            overwrite=args.overwrite,
        )
        print(_json_dump(_cli_summary(result)), end="")
        return 0 if result.get("is_valid") else 2
    except Exception as exc:  # pragma: no cover - exercised through return contract.
        print(_json_dump({"ok": False, "error": str(exc)}), end="", file=sys.stderr)
        return 1


def _write_files(project_dir: Path, files: dict[str, str]) -> list[dict[str, Any]]:
    written = []
    for filename, content in sorted(files.items()):
        target = (project_dir / filename).resolve()
        _assert_within_root(project_dir, target)
        target.write_text(content, encoding="utf-8")
        written.append({"filename": filename, "path": str(target), "bytes": target.stat().st_size})
    return written


def _assert_within_root(root: Path, target: Path) -> None:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Target path escapes output root: {target}") from exc


def _content_type(filename: str) -> str:
    if filename.endswith(".md"):
        return "text/markdown"
    if filename.endswith(".txt"):
        return "text/plain"
    if filename.endswith(".csv"):
        return "text/csv"
    if filename.endswith(".srt"):
        return "application/x-subrip"
    if filename.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _cli_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("is_valid", False),
        "output_dir": result.get("output_dir"),
        "file_count": result.get("file_count", 0),
        "local_only": result.get("local_only", True),
        "deployment_performed": result.get("deployment_performed", False),
        "upload_or_publish_performed": result.get("upload_or_publish_performed", False),
    }


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "api_server_started": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
