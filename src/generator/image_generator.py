"""Fetch segment images from the web (SerpAPI) with copyright-safety filters."""

from __future__ import annotations

import json
from pathlib import Path

from src.config import Settings
from src.generator.models import ProductionPlan
from src.generator.web_image_search import search_and_download


def _segment_query(segment) -> str:
    return (segment.image_search_query or segment.image_prompt or segment.narration).strip()


def _segment_result_offset(segment, used_count: int) -> int:
    if segment.type == "intro":
        return 0
    if segment.image_index is not None:
        return segment.image_index - 1
    return used_count


def generate_images(plan: ProductionPlan, output_dir: Path, settings: Settings) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "image_sources.json"
    if not log_path.exists():
        log_path.write_text("[]", encoding="utf-8")

    paths: dict[str, Path] = {}
    used_urls: set[str] = set()
    fetch_count = 0

    for segment in plan.visual_segments():
        if segment.type == "intro":
            key = "intro"
            out_path = output_dir / "image_intro.png"
            label = "intro"
        else:
            if segment.image_index is None:
                continue
            key = str(segment.image_index)
            out_path = output_dir / f"image_{segment.image_index:02d}.png"
            label = f"image_{segment.image_index:02d}"

        if out_path.exists():
            paths[key] = out_path
            if log_path.exists():
                for entry in json.loads(log_path.read_text(encoding="utf-8")):
                    if entry.get("segment") == label and entry.get("url"):
                        used_urls.add(entry["url"])
            continue

        query = _segment_query(segment)
        print(f"  Searching image: {label} — {query[:60]}...", flush=True)
        search_and_download(
            query=query,
            out_path=out_path,
            settings=settings,
            segment_label=label,
            log_path=log_path,
            result_offset=_segment_result_offset(segment, fetch_count),
            exclude_urls=used_urls,
        )
        fetch_count += 1
        paths[key] = out_path

        if log_path.exists():
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            for entry in reversed(entries):
                if entry.get("segment") == label and entry.get("url"):
                    used_urls.add(entry["url"])
                    break

    return paths
