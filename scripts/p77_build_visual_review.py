#!/usr/bin/env python3
"""Assemble a captioned visual-only review while correct narration is pending."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p68_clip_stitcher import assemble_clip_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    args = parser.parse_args()
    pilot = Path(args.pilots_root) / args.pilot
    artifact = Path(args.artifact_root) / "gold" / args.pilot
    plan = json.loads((pilot / "content-plan.json").read_text(encoding="utf-8"))
    manifests = sorted((artifact / "clips").glob("v*/scientific-animation-manifest.json"))
    if not manifests:
        raise SystemExit("No code-authored animation manifest exists; run p68_render_science.py first")
    clips = json.loads(manifests[-1].read_text(encoding="utf-8"))
    expected = {shot["shot_id"] for shot in plan["shots"]}
    actual = {clip["shot_id"] for clip in clips["clips"]}
    if actual != expected:
        raise SystemExit(f"Visual review requires every planned shot; missing={sorted(expected - actual)}")
    output_dir = artifact / "renders" / "visual-v1"
    output = assemble_clip_plan(plan, clips, output_dir, captions_path=pilot / "captions.srt")
    output.update({
        "review_scope": "visual_motion_and_storyboard_only",
        "narration_required": True,
        "approval_allowed": False,
        "publish_allowed": False,
    })
    (output_dir / "render_manifest.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output.get("is_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
