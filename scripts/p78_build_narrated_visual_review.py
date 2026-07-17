#!/usr/bin/env python3
"""Assemble the gecko visual review with its matching local narration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p68_clip_stitcher import assemble_clip_plan  # noqa: E402
from src.p68_production_pipeline import select_narration  # noqa: E402
from src.p78_kokoro_narration import probe_duration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--pilots-root", type=Path, default=Path("p68-pilots"))
    parser.add_argument("--artifact-root", type=Path, default=Path("p68-artifacts"))
    args = parser.parse_args()
    pilot = args.pilots_root / args.pilot
    artifact = args.artifact_root / "gold" / args.pilot
    plan = json.loads((pilot / "content-plan.json").read_text(encoding="utf-8"))
    manifests = sorted((artifact / "clips").glob("v*/scientific-animation-manifest.json"))
    if not manifests:
        raise SystemExit("Generate the code-authored clips first")
    clips = json.loads(manifests[-1].read_text(encoding="utf-8"))
    narration = select_narration(artifact)
    planned_duration = sum(float(shot["duration_seconds"]) for shot in plan["shots"])
    narration_duration = probe_duration(narration)
    if narration_duration > planned_duration - 0.25:
        raise SystemExit(
            f"Narration is {narration_duration:.3f}s for a {planned_duration:.3f}s plan; regenerate it faster before assembly"
        )
    output_dir = artifact / "renders" / "narrated-visual-v1"
    result = assemble_clip_plan(plan, clips, output_dir, narration_path=narration, captions_path=pilot / "captions.srt")
    result.update({
        "review_scope": "narration_story_motion_and_pacing",
        "hero_shots_require_natural_or_premium_replacement": ["S01", "S06"],
        "narration_duration_seconds": narration_duration,
        "approval_allowed": True,
        "publish_allowed": False,
    })
    (output_dir / "render_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("is_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
