"""P46 local producer export pack generator.

This module converts a P45 pipeline package, or a raw brief that can be passed to
P45, into local producer-facing artifacts. The goal is to help the team create
real videos without deploying infrastructure after every change.

It returns named file payloads and an artifact manifest. It does not write to
cloud storage, deploy, render video, download assets, upload, publish, or call
external APIs.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from src.p45_video_pipeline_orchestrator import run_video_content_pipeline

P46_EXPORT_VERSION = "p46.local_producer_export_pack.v1"


def build_local_export_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Build local production files from a P45 package or raw brief."""

    pipeline = payload if payload.get("schema_version") == "p45.end_to_end_video_pipeline.v1" else run_video_content_pipeline(payload)
    if not pipeline.get("is_valid"):
        return {
            "schema_version": P46_EXPORT_VERSION,
            "is_valid": False,
            "validation_errors": pipeline.get("validation_errors", []),
            "pipeline_package": pipeline,
            **_guardrails(),
        }
    files = {
        "producer_brief.md": render_producer_brief(pipeline),
        "script.txt": render_script_file(pipeline),
        "storyboard.md": render_storyboard(pipeline),
        "shot_list.csv": render_shot_list_csv(pipeline),
        "captions.srt": render_captions_srt(pipeline),
        "metadata.json": render_json(pipeline.get("monetization_report", {}).get("metadata_pack", {})),
        "asset_manifest.json": render_json(build_asset_manifest(pipeline)),
        "review_checklist.md": render_review_checklist(pipeline),
        "platform_variants.json": render_json(build_platform_variants(pipeline)),
    }
    return {
        "schema_version": P46_EXPORT_VERSION,
        "is_valid": True,
        "pipeline_status": pipeline.get("pipeline_status"),
        "artifact_manifest": build_artifact_manifest(files),
        "files": files,
        "pipeline_package": pipeline,
        **_guardrails(),
    }


def render_producer_brief(pipeline: dict[str, Any]) -> str:
    video = pipeline["video_package"]
    brief = video["brief"]
    summary = pipeline["summary"]
    production = pipeline["production_pack"]["production_brief"]
    lines = [
        f"# Producer Brief — {brief['topic']}",
        "",
        f"**Platform:** {brief['platform']}",
        f"**Audience:** {brief['audience']}",
        f"**Duration:** {brief['duration_seconds']}s",
        f"**Pipeline Status:** {pipeline['pipeline_status']}",
        f"**Rights Gate:** {summary['rights_gate']}",
        f"**Engagement Score:** {summary['engagement_score']}",
        f"**Production Ready:** {summary['production_ready']}",
        "",
        "## Objective",
        production.get("objective", f"Produce a video about {brief['topic']}"),
        "",
        "## Hook",
        video.get("hook", ""),
        "",
        "## Best Monetization Routes",
        ", ".join(summary.get("best_monetization_routes", [])) or "TBD",
        "",
        "## Next Actions",
        *[f"- {item}" for item in summary.get("next_actions", [])],
    ]
    return "\n".join(lines).strip() + "\n"


def render_script_file(pipeline: dict[str, Any]) -> str:
    video = pipeline["video_package"]
    return "\n".join(["HOOK:", video.get("hook", ""), "", "SCRIPT:", video.get("script", "")]).strip() + "\n"


def render_storyboard(pipeline: dict[str, Any]) -> str:
    frames = pipeline["production_pack"].get("storyboard_frames", [])
    lines = ["# Storyboard", ""]
    for frame in frames:
        lines.extend([
            f"## Frame {frame['frame_number']} — {frame.get('time_range', '')}",
            f"- Beat: {frame.get('beat', '')}",
            f"- Visual: {frame.get('visual_direction', '')}",
            f"- On-screen text: {frame.get('on_screen_text', '')}",
            f"- Motion: {frame.get('motion_note', '')}",
            f"- Risk note: {frame.get('production_risk_note', '')}",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def render_shot_list_csv(pipeline: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["shot_id", "frame_number", "purpose", "framing", "transition", "caption_style", "asset_need", "editor_note"],
    )
    writer.writeheader()
    for shot in pipeline["production_pack"].get("shot_list", []):
        writer.writerow({key: shot.get(key, "") for key in writer.fieldnames})
    return output.getvalue()


def render_captions_srt(pipeline: dict[str, Any]) -> str:
    rows = []
    for index, item in enumerate(pipeline["production_pack"].get("voiceover_caption_timing", []), start=1):
        start, end = _parse_time_range(item.get("time_range", "0-2s"))
        rows.extend([str(index), f"{_srt_time(start)} --> {_srt_time(end)}", item.get("caption_text", ""), ""])
    return "\n".join(rows).strip() + "\n"


def build_asset_manifest(pipeline: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_checklist": pipeline["production_pack"].get("asset_checklist", []),
        "rights_manifest": pipeline["rights_report"].get("asset_source_manifest", []),
        "rights_gate": pipeline["rights_report"].get("publish_gate", {}),
        "source_evidence_required": True,
    }


def render_review_checklist(pipeline: dict[str, Any]) -> str:
    summary = pipeline["summary"]
    checklist = [
        "# Review Checklist",
        "",
        "- [ ] Creative review completed",
        "- [ ] Rights/source evidence checked",
        "- [ ] Captions proofread",
        "- [ ] Asset manifest completed",
        "- [ ] Platform metadata reviewed",
        "- [ ] Final export QA completed",
        "- [ ] Human approval before upload",
        "",
        f"Pipeline status: {pipeline['pipeline_status']}",
        f"Rights gate: {summary.get('rights_gate')}",
    ]
    return "\n".join(checklist).strip() + "\n"


def build_platform_variants(pipeline: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_platform": pipeline["video_package"]["brief"].get("platform"),
        "variants": pipeline["monetization_report"].get("repurposing_plan", []),
        "notes": "Use these as local adaptation notes only; no upload or platform API call is performed.",
    }


def build_artifact_manifest(files: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "filename": name,
            "content_type": _content_type(name),
            "bytes_estimate": len(content.encode("utf-8")),
            "local_only": True,
        }
        for name, content in files.items()
    ]


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


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


def _parse_time_range(value: str) -> tuple[int, int]:
    numbers = [int(number) for number in re.findall(r"\d+", value)]
    if len(numbers) >= 2:
        return numbers[0], max(numbers[1], numbers[0] + 1)
    if len(numbers) == 1:
        return numbers[0], numbers[0] + 2
    return 0, 2


def _srt_time(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "deployment_performed": False,
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
    }
