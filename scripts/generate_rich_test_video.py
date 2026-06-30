"""Generate a richer test video with scene changes and loud audio bursts."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def generate_rich_test_video(output_path: Path) -> None:
    """Concatenate short clips with different visuals and audio levels."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        segments: list[Path] = []
        specs = [
            ("red", 440, 15),
            ("green", 880, 15),
            ("blue", 220, 15),
            ("yellow", 660, 15),
        ]
        list_file = tmp_path / "segments.txt"

        for index, (color, freq, duration) in enumerate(specs):
            segment = tmp_path / f"seg_{index}.mp4"
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s=640x360:d={duration}:r=30",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={freq}:duration={duration}",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    str(segment),
                ]
            )
            segments.append(segment)

        list_file.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in segments),
            encoding="utf-8",
        )
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output_path),
            ]
        )


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/input/rich_test_match.mp4")
    generate_rich_test_video(out)
    print(f"Created {out}")
