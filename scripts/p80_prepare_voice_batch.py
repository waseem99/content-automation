#!/usr/bin/env python3
"""Prepare and attach local Kokoro narration for a bounded month-review batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BRAND_STYLES = {
    "rawr-nation": ("#FFD84D", "#70D6FF", "Real facts. Clear reveals.", "energetic, curious, factual"),
    "animal-x": ("#8CE99A", "#74C0FC", "Signals hidden in plain sight.", "observant, intelligent, intriguing"),
    "historiq": ("#D6B36A", "#8C7AA9", "The evidence behind the story.", "cinematic, measured, historically credible"),
    "ani-films": ("#FF8A65", "#64B5F6", "Complex ideas, clearly moving.", "clear, visual, confidently explanatory"),
}


def brand_payload(studio: dict) -> dict:
    slug = studio["brand"]["slug"]
    primary, secondary, tagline, tone = BRAND_STYLES.get(slug, ("#FFD84D", "#70D6FF", "Clear visual stories.", "clear and credible"))
    name = studio["brand"]["name"]
    return {"id": slug.replace("-", "_"), "name": name, "tagline": tagline, "primaryColor": primary, "secondaryColor": secondary, "backgroundColor": "#0B1018", "captionColor": "#FFFFFF", "watermark": name.upper(), "tone": tone, "voiceStyle": "clear, quick international English narrator"}


def prepare(studio_path: Path, output: Path, limit: int) -> list[Path]:
    studio = json.loads(studio_path.read_text(encoding="utf-8"))
    brand = brand_payload(studio)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in studio["items"][:limit]:
        project = {
            "schemaVersion": "p65.video_project.v1", "id": item["id"], "title": item["title"],
            "brand": brand, "format": "vertical_short", "compositionId": "ReferenceStoryShort",
            "visualTheme": "abstract", "narration": item["script"]["narration"],
            "scenes": [
                {"id": f"scene-{scene['scene']}", "startSec": scene["start_seconds"], "endSec": scene["end_seconds"],
                 "headline": scene["purpose"].replace("_", " ").upper(), "body": scene["narration"],
                 "visual": "hook" if scene["scene"] == 1 else "cta" if scene["scene"] == 5 else "bridge",
                 "accent": brand["primaryColor"], "safetyLevel": "pending_human_review", "objectives": ["engagement", "compliance"]}
                for scene in item["scene_plan"]
            ],
            "captions": [
                {"startSec": scene["start_seconds"], "endSec": scene["end_seconds"],
                 "text": scene["narration"], "highlight": scene["narration"].split()[-1].strip(".,!?"), "emphasis": "fact"}
                for scene in item["scene_plan"]
            ],
            "sources": [],
            "render": {"width": 1080, "height": 1920, "fps": 30, "codec": "h264", "durationSeconds": item["duration_seconds"]},
            "disclosure": "Original narration draft · human fact and creative review required",
            "callToAction": item["platform_packages"][0]["cta"], "humanReviewRequired": True,
            "editorialStatus": "draft_for_human_review",
        }
        path = output / f"{item['id']}.json"
        path.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def attach(studio_path: Path, media_dir: Path, limit: int) -> int:
    studio = json.loads(studio_path.read_text(encoding="utf-8"))
    attached = 0
    for item in studio["items"][:limit]:
        name = f"{item['id']}-kokoro.wav"
        if not (media_dir / name).is_file():
            continue
        item["voice"].update({
            "status": "ready_for_review",
            "delivery": "operator_api_artifact",
            "review_required": True,
        })
        item["voice"].pop("preview_url", None)
        item["review"]["voice"] = "ready_for_review"
        attached += 1
    studio["summary"]["voice_previews_ready"] = attached
    studio_path.write_text(json.dumps(studio, indent=2) + "\n", encoding="utf-8")
    return attached


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "attach"))
    parser.add_argument("--studio", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    parser.add_argument("--projects", type=Path, default=Path(".local-production/rawr-month-projects"))
    parser.add_argument("--media", type=Path, default=Path("web/static-creator-ui/media/rawr-nation/voice"))
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    if args.mode == "prepare":
        paths = prepare(args.studio, args.projects, args.limit)
        print(json.dumps({"prepared": [str(path) for path in paths]}))
    else:
        count = attach(args.studio, args.media, args.limit)
        print(json.dumps({"attached": count}))
        if count != args.limit:
            raise SystemExit(f"Expected {args.limit} narration files, attached {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
