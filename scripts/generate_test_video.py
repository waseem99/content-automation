"""Generate a short synthetic test video for pipeline smoke tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def generate_test_video(output_path: Path, duration_sec: int = 30) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_sec}:size=640x360:rate=30",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_sec}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/input/test_match.mp4")
    generate_test_video(out)
    print(f"Created {out}")
