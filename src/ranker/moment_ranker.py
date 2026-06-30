"""Merge scene, audio, and transcript signals into ranked clip windows."""

from __future__ import annotations

from dataclasses import dataclass

from src.analyzer.audio_analyzer import EnergySpike
from src.analyzer.scene_detector import SceneBoundary
from src.analyzer.topic_matcher import ScoredSegment
from src.config import Settings
from src.extractor.ffmpeg_clipper import ClipWindow


@dataclass
class Anchor:
    time_sec: float
    topic_score: float = 0.0
    energy_score: float = 0.0
    scene_score: float = 0.0
    label: str = "moment"
    source_text: str = ""


def _build_window(
    anchor_time: float,
    duration: float,
    lead_in: float,
    video_duration: float,
) -> tuple[float, float]:
    start = max(0.0, anchor_time - lead_in)
    end = min(video_duration, start + duration)
    if end - start < duration * 0.5:
        start = max(0.0, end - duration)
    return start, end


def _windows_overlap(a: ClipWindow, b: ClipWindow, min_gap: float) -> bool:
    gap = max(a.start, b.start) - min(a.end, b.end)
    return gap < min_gap


def _merge_anchors(
    scenes: list[SceneBoundary],
    energy_spikes: list[EnergySpike],
    transcript_hits: list[ScoredSegment],
    scene_proximity_sec: float = 5.0,
) -> list[Anchor]:
    anchors: dict[int, Anchor] = {}

    def bucket(time_sec: float) -> int:
        return int(time_sec // 2)

    def upsert(time_sec: float, **kwargs) -> None:
        key = bucket(time_sec)
        existing = anchors.get(key)
        if existing is None:
            anchors[key] = Anchor(time_sec=time_sec, **kwargs)
            return
        for field, value in kwargs.items():
            current = getattr(existing, field)
            if isinstance(value, (int, float)) and value > current:
                setattr(existing, field, value)
            elif isinstance(value, str) and value and not current:
                setattr(existing, field, value)

    for hit in transcript_hits:
        center = (hit.start + hit.end) / 2
        upsert(
            center,
            topic_score=hit.topic_score,
            label=hit.label,
            source_text=hit.text,
        )

    for spike in energy_spikes:
        upsert(spike.time_sec, energy_score=spike.score, label="crowd_reaction")

    scene_times = [s.time_sec for s in scenes]
    for scene in scenes:
        nearby_topic = 0.0
        for hit in transcript_hits:
            if abs(((hit.start + hit.end) / 2) - scene.time_sec) <= scene_proximity_sec:
                nearby_topic = max(nearby_topic, hit.topic_score)
        scene_score = 0.6 + (0.4 * nearby_topic)
        upsert(
            scene.time_sec,
            scene_score=scene_score,
            topic_score=max(
                nearby_topic,
                anchors.get(bucket(scene.time_sec), Anchor(time_sec=scene.time_sec)).topic_score,
            ),
        )

    # Boost anchors that sit near both energy spike and scene cut
    for anchor in anchors.values():
        if any(abs(anchor.time_sec - t) <= 3 for t in scene_times) and anchor.energy_score > 0:
            anchor.energy_score = min(1.0, anchor.energy_score + 0.15)

    return list(anchors.values())


def _effective_min_gap(settings: Settings, video_duration: float) -> float:
    if video_duration <= 0:
        return settings.min_gap
    spacing = video_duration / max(1, settings.clip_count)
    return min(settings.min_gap, max(settings.clip_duration, spacing * 0.6))


def _evenly_spaced_anchors(
    video_duration: float,
    count: int,
    existing: list[ClipWindow],
    settings: Settings,
) -> list[ClipWindow]:
    if count <= 0 or video_duration <= 0:
        return []

    gap = _effective_min_gap(settings, video_duration)
    margin = settings.clip_duration + settings.clip_lead_in
    start_at = margin
    end_at = max(margin, video_duration - settings.clip_duration)
    if end_at <= start_at:
        return []

    step = (end_at - start_at) / max(1, count)
    extras: list[ClipWindow] = []
    for index in range(count):
        anchor_time = start_at + (step * index)
        start, end = _build_window(
            anchor_time,
            settings.clip_duration,
            settings.clip_lead_in,
            video_duration,
        )
        candidate = ClipWindow(start=start, end=end, score=0.1, label="moment")
        if any(_windows_overlap(candidate, chosen, gap) for chosen in existing + extras):
            continue
        extras.append(candidate)
    return extras


def rank_moments(
    scenes: list[SceneBoundary],
    energy_spikes: list[EnergySpike],
    transcript_hits: list[ScoredSegment],
    video_duration: float,
    settings: Settings,
) -> list[ClipWindow]:
    anchors = _merge_anchors(scenes, energy_spikes, transcript_hits)

    if not anchors:
        # Fallback: evenly spaced high-energy or scene anchors
        fallback_times = [s.time_sec for s in scenes[:10]] or [video_duration * 0.25]
        anchors = [Anchor(time_sec=t, scene_score=0.5, label="moment") for t in fallback_times]

    windows: list[ClipWindow] = []
    for anchor in anchors:
        composite = (
            settings.topic_weight * anchor.topic_score
            + settings.energy_weight * anchor.energy_score
            + settings.scene_weight * anchor.scene_score
        )
        start, end = _build_window(
            anchor.time_sec,
            settings.clip_duration,
            settings.clip_lead_in,
            video_duration,
        )
        windows.append(
            ClipWindow(
                start=start,
                end=end,
                score=composite,
                label=anchor.label,
                source_text=anchor.source_text,
            )
        )

    windows.sort(key=lambda w: w.score, reverse=True)
    min_gap = _effective_min_gap(settings, video_duration)

    selected: list[ClipWindow] = []
    for window in windows:
        if window.score <= 0 and selected:
            continue
        if any(_windows_overlap(window, chosen, min_gap) for chosen in selected):
            continue
        selected.append(window)
        if len(selected) >= settings.clip_count:
            break

    if len(selected) < settings.clip_count:
        relaxed_gap = min_gap * 0.5
        for window in windows:
            if window in selected:
                continue
            if any(_windows_overlap(window, chosen, relaxed_gap) for chosen in selected):
                continue
            selected.append(window)
            if len(selected) >= settings.clip_count:
                break

    if len(selected) < settings.clip_count:
        selected.extend(
            _evenly_spaced_anchors(
                video_duration,
                settings.clip_count - len(selected),
                selected,
                settings,
            )
        )

    return sorted(selected[: settings.clip_count], key=lambda w: w.start)
