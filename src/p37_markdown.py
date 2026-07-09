"""P37 Markdown-only local review packet renderer.

Renders P36 packet metadata into Markdown strings only. No HTML/PDF, archives,
delivery, upload, sync, network, scheduler, credentials, platform edits,
deletion, movement, or publishing.
"""

from __future__ import annotations

from typing import Any

P37_RENDER_VERSION = "p37.markdown_renderer.v1"

GUARDRAILS = {
    "markdown_only": True,
    "html_rendered": False,
    "pdf_rendered": False,
    "zip_created": False,
    "email_sent": False,
    "slack_sent": False,
    "cloud_sync": False,
    "external_upload": False,
    "network_called": False,
    "scheduler_used": False,
    "credentials_used": False,
    "platform_edit_performed": False,
    "deletion_performed": False,
    "moving_performed": False,
    "publish_allowed": False,
    "review_required": True,
}


def _bullet(items: list[Any]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def render_packet_overview(packet: dict[str, Any]) -> str:
    counts = packet.get("counts", {})
    lines = [
        f"# {packet.get('packet_title', 'Local Review Packet')}",
        "",
        f"Packet ID: `{packet.get('packet_id', 'unknown')}`",
        f"Generated at: `{packet.get('generated_at', 'manual')}`",
        "",
        "## Counts",
        f"- Total items: {counts.get('total_items', 0)}",
        f"- Required items: {counts.get('required_items', 0)}",
        "",
        "## Warnings",
        _bullet(packet.get("warnings", [])),
        "",
        "## Guardrails",
        "- Markdown-only local output.",
        "- No HTML/PDF, ZIP/archive, delivery, sync, upload, network, scheduler, credentials, platform edit, deletion, movement, or publishing.",
    ]
    return "\n".join(lines) + "\n"


def render_item_table(packet: dict[str, Any]) -> str:
    lines = [
        "# Packet Items",
        "",
        "| Section | Title | Type | Path | Status | Reviewer | Required | Checksum |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in packet.get("items", []):
        lines.append(
            "| {section} | {title} | {item_type} | `{path}` | {status} | {reviewer} | {required} | `{checksum}` |".format(
                section=item.get("section", ""),
                title=item.get("title", ""),
                item_type=item.get("item_type", ""),
                path=item.get("relative_path", ""),
                status=item.get("review_status", ""),
                reviewer=item.get("reviewer_role", ""),
                required="yes" if item.get("required") else "no",
                checksum=item.get("checksum_digest") or "none",
            )
        )
    return "\n".join(lines) + "\n"


def render_reviewer_checklist(checklist: dict[str, Any]) -> str:
    lines = [
        f"# Reviewer Checklist — {checklist.get('checklist_id', 'unknown')}",
        "",
        f"Reviewer role: `{checklist.get('reviewer_role', 'unknown')}`",
        "",
        "## Gates",
        _bullet(checklist.get("gates", [])),
        "",
        "## Required items",
        _bullet(checklist.get("required_items", [])),
        "",
        "## Decision options",
        _bullet(checklist.get("decision_options", [])),
        "",
        "Approval mode: `human_only_local_review`",
    ]
    return "\n".join(lines) + "\n"


def render_blocker_appendix(appendix: dict[str, Any]) -> str:
    lines = [
        f"# Blocker Appendix — {appendix.get('appendix_id', 'unknown')}",
        "",
        "| Type | Severity | Source item | Owner | Resolution | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for blocker in appendix.get("blockers", []):
        lines.append(
            "| {blocker_type} | {severity} | {source} | {owner} | {resolution} | {notes} |".format(
                blocker_type=blocker.get("blocker_type", ""),
                severity=blocker.get("severity", ""),
                source=blocker.get("source_item_id", ""),
                owner=blocker.get("owner_role", ""),
                resolution=blocker.get("required_resolution", ""),
                notes=blocker.get("reviewer_notes", ""),
            )
        )
    lines += ["", "No automated remediation, deletion, upload, or publishing action was performed."]
    return "\n".join(lines) + "\n"


def render_local_handoff(manifest: dict[str, Any]) -> str:
    lines = [
        f"# Local Handoff — {manifest.get('manifest_id', 'unknown')}",
        "",
        f"Packet ID: `{manifest.get('packet_id', 'unknown')}`",
        f"Distribution: `{manifest.get('distribution_status', 'local_only_not_sent')}`",
        "",
        "## Packet files",
        _bullet(manifest.get("packet_files", [])),
        "",
        "## Reviewer roles",
        _bullet(manifest.get("reviewer_roles", [])),
        "",
        "## Checklist IDs",
        _bullet(manifest.get("checklist_ids", [])),
        "",
        "## Blocker appendices",
        _bullet(manifest.get("blocker_appendices", [])),
        "",
        "## Next local steps",
        _bullet(manifest.get("next_local_steps", [])),
    ]
    return "\n".join(lines) + "\n"


def render_full_markdown_packet(packet: dict[str, Any], checklists: list[dict[str, Any]], appendices: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    sections = [render_packet_overview(packet), render_item_table(packet)]
    sections.extend(render_reviewer_checklist(item) for item in checklists)
    sections.extend(render_blocker_appendix(item) for item in appendices)
    sections.append(render_local_handoff(manifest))
    markdown = "\n---\n\n".join(sections)
    return {
        "schema_version": P37_RENDER_VERSION,
        "markdown": markdown,
        "section_count": len(sections),
        **GUARDRAILS,
    }
