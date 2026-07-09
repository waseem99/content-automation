"""P38 Markdown-only navigation helpers for local review packets."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

P38_NAV_VERSION = "p38.markdown_navigation.v1"

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


def slugify_heading(text: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", text.lower()).strip()
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug or "section"


def render_section_anchors(headings: list[str]) -> list[dict[str, str]]:
    seen: Counter[str] = Counter()
    anchors = []
    for heading in headings:
        base = slugify_heading(heading)
        seen[base] += 1
        anchor = base if seen[base] == 1 else f"{base}-{seen[base] - 1}"
        anchors.append({"heading": heading, "anchor": anchor, "link": f"#{anchor}"})
    return anchors


def render_packet_toc(headings: list[str]) -> str:
    anchors = render_section_anchors(headings)
    lines = ["# Table of Contents", ""]
    lines.extend(f"- [{item['heading']}]({item['link']})" for item in anchors)
    return "\n".join(lines) + "\n"


def render_reviewer_quick_links(checklists: list[dict[str, Any]]) -> str:
    lines = ["# Reviewer Quick Links", ""]
    for checklist in checklists:
        title = f"Checklist {checklist.get('checklist_id', 'unknown')} — {checklist.get('reviewer_role', 'reviewer')}"
        lines.append(f"- [{title}](#{slugify_heading(title)})")
    return "\n".join(lines) + "\n"


def render_blocker_quick_links(appendices: list[dict[str, Any]]) -> str:
    lines = ["# Blocker Quick Links", ""]
    for appendix in appendices:
        title = f"Blocker Appendix {appendix.get('appendix_id', 'unknown')}"
        lines.append(f"- [{title}](#{slugify_heading(title)})")
    return "\n".join(lines) + "\n"


def render_navigation_summary(headings: list[str], checklists: list[dict[str, Any]], appendices: list[dict[str, Any]]) -> dict[str, Any]:
    markdown = "\n".join(
        [
            render_packet_toc(headings).rstrip(),
            "---",
            render_reviewer_quick_links(checklists).rstrip(),
            "---",
            render_blocker_quick_links(appendices).rstrip(),
            "---",
            "## Guardrails\n- Markdown-only local navigation.\n- No HTML/PDF, ZIP, delivery, sync, upload, network, scheduler, credentials, platform edit, deletion, movement, or publishing.",
        ]
    ) + "\n"
    return {
        "schema_version": P38_NAV_VERSION,
        "markdown": markdown,
        "heading_count": len(headings),
        "checklist_count": len(checklists),
        "appendix_count": len(appendices),
        **GUARDRAILS,
    }
