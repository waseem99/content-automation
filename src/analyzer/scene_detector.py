"""Scene boundary detection via PySceneDetect."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video


@dataclass
class SceneBoundary:
    time_sec: float
    frame_number: int


def detect_scenes(video_path: Path, threshold: float = 27.0) -> list[SceneBoundary]:
    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video)

    boundaries: list[SceneBoundary] = []
    for scene in scene_manager.get_scene_list():
        start_time, _ = scene
        boundaries.append(
            SceneBoundary(
                time_sec=start_time.get_seconds(),
                frame_number=start_time.get_frames(),
            )
        )
    return boundaries
