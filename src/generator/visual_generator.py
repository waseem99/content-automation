"""Route visual beats to SerpAPI web images or OpenAI AI images."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from openai import BadRequestError

from src.config import Settings
from src.generator.collage_builder import build_four_player_collage
from src.generator.entity_matcher import ENTITY_NAME_HINTS
from src.generator.ai_image_generator import generate_ai_image
from src.generator.image_editor import apply_cinematic_edit
from src.generator.models import ExplainerPlan
from src.generator.prompt_sanitizer import DEFAULT_CINEMATIC_EDIT_PROMPT, sanitize_ai_prompt
from src.generator.web_image_search import search_and_download


def _beat_path(production_dir: Path, section_id: str, beat_index: int) -> Path:
    return production_dir / f"beat_{section_id}_{beat_index:02d}.png"


def _entity_for_search(section, query: str) -> str:
    if section.entity_name:
        return section.entity_name
    query_lower = query.lower()
    for name in ENTITY_NAME_HINTS:
        if name.lower().split()[-1] in query_lower or name.lower() in query_lower:
            return name
    return ""


def _fetch_web_image(
    beat,
    section,
    key: str,
    out_path: Path,
    settings: Settings,
    log_path: Path,
    fetch_count: int,
    used_urls: set[str],
) -> Path:
    query = (
        beat.image_search_query
        or beat.ai_image_prompt
        or f"{section.entity_name} World Cup 2026"
        or "World Cup football editorial"
    ).strip()
    print(f"  Web image: {section.id} — {query[:50]}...", flush=True)
    entity_name = _entity_for_search(section, query)

    src_path = out_path.with_suffix(".src.png")
    search_and_download(
        query=query,
        out_path=src_path,
        settings=settings,
        segment_label=key,
        log_path=log_path,
        result_offset=fetch_count,
        exclude_urls=used_urls,
        entity_name=entity_name,
    )

    if beat.cinematic_edit or section.section_type in ("comparison", "cta"):
        edit_prompt = beat.cinematic_edit_prompt or settings.cinematic_edit_prompt
        print(f"  Cinematic edit: {section.id}...", flush=True)
        apply_cinematic_edit(src_path, out_path, settings, edit_prompt=edit_prompt)
        if src_path.exists() and src_path != out_path:
            src_path.unlink()
        return out_path

    if src_path != out_path:
        src_path.replace(out_path)
    return out_path


COMPARISON_COLLAGE_FILENAME = "beat_comparison_collage.png"


def _maybe_build_comparison_collage(
    section,
    production_dir: Path,
    paths: dict[str, Path],
) -> None:
    if section.section_type != "comparison":
        return
    panel_paths = [
        paths.get(f"{section.id}_{index:02d}")
        or production_dir / f"beat_{section.id}_{index:02d}.png"
        for index in range(4)
    ]
    if not all(path and path.exists() for path in panel_paths):
        return
    out_path = production_dir / COMPARISON_COLLAGE_FILENAME
    print(f"  Building comparison collage: {out_path.name}", flush=True)
    build_four_player_collage(panel_paths, out_path)
    paths["comparison_collage"] = out_path


def generate_explainer_visuals(
    plan: ExplainerPlan,
    production_dir: Path,
    settings: Settings,
    force_regenerate: bool = False,
    on_beat_complete: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    """Return map of beat_key -> image path. beat_key = '{section_id}_{beat_index}'."""
    production_dir.mkdir(parents=True, exist_ok=True)
    log_path = production_dir / "image_sources.json"
    if not log_path.exists():
        log_path.write_text("[]", encoding="utf-8")

    paths: dict[str, Path] = {}
    used_urls: set[str] = set()
    fetch_count = 0

    for section in plan.sections:
        for beat_index, beat in enumerate(section.beats):
            if beat.visual_type == "clip":
                continue

            key = f"{section.id}_{beat_index:02d}"
            out_path = _beat_path(production_dir, section.id, beat_index)

            if out_path.exists() and not force_regenerate:
                print(f"  Reusing image: {out_path.name}", flush=True)
                paths[key] = out_path
                if on_beat_complete:
                    on_beat_complete(key)
                continue

            if force_regenerate and out_path.exists():
                out_path.unlink()

            if beat.visual_type == "ai_image":
                raw_prompt = beat.ai_image_prompt or beat.image_search_query
                if not raw_prompt and section.entity_name:
                    raw_prompt = (
                        f"Stylized editorial football illustration, {section.theme}, "
                        f"national colors, no official badges"
                    )
                prompt = sanitize_ai_prompt(raw_prompt)
                print(f"  AI image: {section.id} beat {beat_index} — {prompt[:50]}...", flush=True)
                try:
                    generate_ai_image(prompt, out_path, settings)
                    _append_log(
                        log_path,
                        {
                            "beat_key": key,
                            "section": section.id,
                            "type": "ai_image",
                            "prompt": prompt,
                            "path": str(out_path.name),
                        },
                    )
                except BadRequestError as exc:
                    if "moderation" not in str(exc).lower():
                        raise
                    print(
                        f"  AI blocked (public figure). Using SerpAPI + cinematic edit for {key}...",
                        flush=True,
                    )
                    beat.visual_type = "web_image"
                    if not beat.image_search_query:
                        beat.image_search_query = (
                            f"{section.entity_name or section.theme or 'World Cup'} "
                            "football editorial photo"
                        ).strip()
                    beat.cinematic_edit = True
                    beat.cinematic_edit_prompt = DEFAULT_CINEMATIC_EDIT_PROMPT
                    _fetch_web_image(
                        beat, section, key, out_path, settings, log_path, fetch_count, used_urls
                    )
                    _append_log(
                        log_path,
                        {
                            "beat_key": key,
                            "section": section.id,
                            "type": "web_image_cinematic_fallback",
                            "query": beat.image_search_query,
                            "path": str(out_path.name),
                        },
                    )
                paths[key] = out_path
                if on_beat_complete:
                    on_beat_complete(key)
                continue

            try:
                _fetch_web_image(
                    beat, section, key, out_path, settings, log_path, fetch_count, used_urls
                )
            except Exception as exc:
                if not settings.web_image_fallback_to_ai:
                    raise
                prompt = sanitize_ai_prompt(
                    beat.ai_image_prompt
                    or f"Stylized editorial football illustration, {section.theme}, "
                    "national colors, no official badges"
                )
                print(
                    f"  Web image failed ({exc}). Falling back to AI image for {key}...",
                    flush=True,
                )
                try:
                    generate_ai_image(prompt, out_path, settings)
                except BadRequestError:
                    raise RuntimeError(
                        f"Web and AI both failed for {key}. Place beat_{section.id}_{beat_index:02d}.png manually."
                    ) from exc
                _append_log(
                    log_path,
                    {
                        "beat_key": key,
                        "section": section.id,
                        "type": "ai_image_fallback",
                        "prompt": prompt,
                        "path": str(out_path.name),
                        "web_error": str(exc),
                    },
                )

            fetch_count += 1
            paths[key] = out_path
            if on_beat_complete:
                on_beat_complete(key)

            if log_path.exists():
                entries = json.loads(log_path.read_text(encoding="utf-8"))
                for entry in reversed(entries):
                    if entry.get("segment") == key and entry.get("url"):
                        used_urls.add(entry["url"])
                        break

        _maybe_build_comparison_collage(section, production_dir, paths)

    return paths


def _append_log(log_path: Path, entry: dict) -> None:
    entries: list = []
    if log_path.exists():
        entries = json.loads(log_path.read_text(encoding="utf-8"))
    entries.append(entry)
    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
