from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def analyze_every_frame(video: Path, workspace: Path) -> dict[str, Any]:
    """Decode every video frame and measure visual change without retaining frame copies."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install the media extra for every-frame analysis") from exc

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not decode {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 30.0
    measured: list[dict[str, Any]] = []
    previous = None
    frame_number = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
            brightness = float(small.mean()) / 255.0
            change = (
                float(cv2.absdiff(small, previous).mean()) / 255.0
                if previous is not None
                else 0.0
            )
            measured.append(
                {
                    "frame": frame_number,
                    "timestamp_seconds": round(frame_number / fps, 4),
                    "change_score": round(change, 5),
                    "brightness": round(brightness, 5),
                }
            )
            previous = small
            frame_number += 1
    finally:
        capture.release()

    changes = [item["change_score"] for item in measured[1:]]
    if changes:
        median = statistics.median(changes)
        deviation = statistics.median(abs(value - median) for value in changes)
        cut_threshold = max(0.12, median + (6 * deviation))
    else:
        cut_threshold = 0.12
    cuts = [
        {
            "frame": item["frame"],
            "timestamp_seconds": item["timestamp_seconds"],
            "change_score": item["change_score"],
        }
        for item in measured
        if item["change_score"] >= cut_threshold
    ]
    static_ratio = (
        sum(item["change_score"] < 0.003 for item in measured[1:]) / max(len(measured) - 1, 1)
    )
    payload = {
        "schema_version": "p74.every_frame_metrics.v1",
        "video": str(video.name),
        "decoder": "opencv",
        "fps": round(fps, 4),
        "frame_count": len(measured),
        "duration_seconds": round(len(measured) / fps, 4),
        "cut_threshold": round(cut_threshold, 5),
        "candidate_cut_count": len(cuts),
        "candidate_cuts": cuts,
        "mean_change_score": round(statistics.mean(changes), 5) if changes else 0.0,
        "median_change_score": round(statistics.median(changes), 5) if changes else 0.0,
        "static_frame_ratio": round(static_ratio, 5),
        "frames": measured,
        "interpretation": {
            "candidate_cuts_are_measurements_not_editorial_labels": True,
            "frames_are_not_retained": True,
            "scene_keyframes_and_contact_sheet_are_stored_separately": True,
        },
    }
    target = workspace / "frames" / "every_frame_metrics.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
