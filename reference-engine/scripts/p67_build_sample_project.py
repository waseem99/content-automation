from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def distribute_boundaries(duration: float, weights: list[float]) -> list[tuple[float, float]]:
    total = sum(max(weight, 0.01) for weight in weights)
    cursor = 0.0
    ranges: list[tuple[float, float]] = []
    for index, weight in enumerate(weights):
        end = duration if index == len(weights) - 1 else cursor + duration * max(weight, 0.01) / total
        ranges.append((round(cursor, 3), round(end, 3)))
        cursor = end
    return ranges


def retime_items(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    original_duration = max(float(item["endSec"]) for item in items)
    scale = duration / original_duration
    output = json.loads(json.dumps(items))
    for item in output:
        item["startSec"] = round(float(item["startSec"]) * scale, 3)
        item["endSec"] = round(float(item["endSec"]) * scale, 3)
    output[-1]["endSec"] = round(duration, 3)
    return output


def build_project(
    fingerprint: dict[str, Any],
    brief: dict[str, Any],
    template: dict[str, Any],
) -> dict[str, Any]:
    if brief.get("human_review_required") is not True:
        raise ValueError("Original brief must require human review")
    constraints = brief.get("originality_constraints") or []
    required_constraints = {
        "exact script wording",
        "source footage and frame composition",
        "source branding, logos, and watermarks",
    }
    if not required_constraints.issubset(set(constraints)):
        raise ValueError("Original brief does not contain the required anti-copy constraints")

    project = json.loads(json.dumps(template))
    duration = float(brief.get("duration_seconds") or template["render"]["durationSeconds"])
    duration = min(60.0, max(15.0, duration))
    project["render"]["durationSeconds"] = duration
    project["scenes"] = retime_items(project["scenes"], duration)
    project["captions"] = retime_items(project["captions"], duration)
    project["editorialStatus"] = "demo_only_not_approved"
    project["humanReviewRequired"] = True
    project["referenceInfluence"] = {
        "schemaVersion": "p67.reference_influence.v1",
        "referenceId": fingerprint.get("reference_id"),
        "referenceTitle": fingerprint.get("title"),
        "mechanicsOnly": True,
        "hookType": fingerprint.get("hook", {}).get("hook_type"),
        "referenceVisualChangesPerMinute": fingerprint.get("pacing", {}).get(
            "visual_changes_per_minute"
        ),
        "referenceCaptionChangesPerMinute": fingerprint.get("pacing", {}).get(
            "caption_changes_per_minute"
        ),
        "reusableMechanics": fingerprint.get("reusable_mechanics", []),
        "excludedSourceElements": constraints,
        "sourceMediaUsedInRender": False,
        "humanReviewRequired": True,
    }
    project["disclosure"] = (
        "Original production inspired by abstract pacing mechanics · human review required"
    )
    return project


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fingerprint", type=Path, required=True)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    fingerprint = json.loads(args.fingerprint.read_text(encoding="utf-8"))
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    template = json.loads(args.template.read_text(encoding="utf-8"))
    project = build_project(fingerprint, brief, template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(project, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
