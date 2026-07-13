"""Build review-blocked P68 gold-pilot production packs from source briefs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.p68_continuity_planner import build_original_content_plan, continuity_bible


BRANDS = {
    "rawr_nation": {
        "id": "rawr_nation",
        "name": "Rawr Nation",
        "tagline": "Real facts. Clear reveals.",
        "primaryColor": "#FFD84D",
        "secondaryColor": "#70D6FF",
        "backgroundColor": "#0B1018",
        "captionColor": "#FFFFFF",
        "watermark": "RAWR NATION",
        "tone": "energetic, curious, factual",
        "voiceStyle": "clear, quick international English narrator",
    },
    "animal_x": {
        "id": "animal_x",
        "name": "Animal X",
        "tagline": "Wild behavior. Clearly explained.",
        "primaryColor": "#D6B56D",
        "secondaryColor": "#87B8A2",
        "backgroundColor": "#101814",
        "captionColor": "#FFFFFF",
        "watermark": "ANIMAL X",
        "tone": "cinematic, respectful, factual",
        "voiceStyle": "warm restrained wildlife-documentary narrator",
    },
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def prepare_brief(path: Path) -> dict[str, Any]:
    brief = _load(path)
    bible = continuity_bible(**brief["continuity_bible"])
    plan = build_original_content_plan(
        topic=brief["topic"],
        brand_profile=brief["brand_profile"],
        reusable_mechanics=brief["reusable_mechanics"],
        selected_concept_id=brief["selected_concept_id"],
        script_segments=brief["script_segments"],
        bible=bible,
        factual_notes=brief["factual_notes"],
        source_phrases=brief.get("source_phrases_for_originality_check", []),
    )
    plan["pilot_id"] = brief["pilot_id"]
    plan["source_brief_path"] = str(path)
    plan["render_allowed"] = False
    plan["publish_allowed"] = False
    target = path.parent / "content-plan.json"
    target.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (path.parent / "script.md").write_text(
        f"# {brief['pilot_id']} — Original Narration\n\n{plan['original_script']}\n",
        encoding="utf-8",
    )
    (path.parent / "storyboard.json").write_text(
        json.dumps(plan["storyboard"], indent=2),
        encoding="utf-8",
    )
    (path.parent / "clip-prompts.json").write_text(
        json.dumps(
            [
                {
                    "shot_id": shot["shot_id"],
                    "prompt": shot["clip_prompt"],
                    "negative_prompt": shot["negative_prompt"],
                    "entry_action": shot["entry_action"],
                    "exit_action": shot["exit_action"],
                }
                for shot in plan["shots"]
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    voice_project = {
        "id": brief["pilot_id"],
        "brand": BRANDS[brief["brand_profile"]],
        "narration": plan["original_script"],
        "render": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "codec": "h264",
            "durationSeconds": sum(shot["duration_seconds"] for shot in plan["shots"]),
        },
        "scenes": [
            {
                "id": shot["shot_id"],
                "startSec": shot["start_seconds"],
                "endSec": shot["end_seconds"],
                "headline": shot["caption"],
                "body": shot["narration"],
                "visual": "generated_clip",
                "accent": BRANDS[brief["brand_profile"]]["primaryColor"],
                "safetyLevel": "pending_human_review",
                "objectives": ["engagement", "compliance"],
            }
            for shot in plan["shots"]
        ],
        "captions": [
            {
                "startSec": shot["start_seconds"],
                "endSec": shot["end_seconds"],
                "text": shot["caption"],
                "highlight": shot["caption"].split()[-1],
                "emphasis": "fact",
            }
            for shot in plan["shots"]
        ],
        "editorialStatus": "draft_for_human_review",
        "humanReviewRequired": True,
        "publishAllowed": False,
    }
    (path.parent / "voice-project.json").write_text(
        json.dumps(voice_project, indent=2),
        encoding="utf-8",
    )
    srt_blocks = []
    for index, shot in enumerate(plan["shots"], start=1):
        srt_blocks.append(
            f"{index}\n{_srt_time(shot['start_seconds'])} --> "
            f"{_srt_time(shot['end_seconds'])}\n{shot['caption']}\n"
        )
    (path.parent / "captions.srt").write_text("\n".join(srt_blocks), encoding="utf-8")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="p68-pilots")
    args = parser.parse_args()
    root = Path(args.root)
    paths = sorted(root.glob("*/source-brief.json"))
    if not paths:
        raise SystemExit(f"No gold-pilot source briefs found under {root}")
    plans = [prepare_brief(path) for path in paths]
    failures = [plan["pilot_id"] for plan in plans if not plan["validation"]["passed"]]
    print(json.dumps({"prepared": [plan["pilot_id"] for plan in plans], "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
