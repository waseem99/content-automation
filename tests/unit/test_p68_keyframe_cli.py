from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cli_writes_one_shot_low_vram_plan(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/p68_generate_keyframes.py"),
            "plan",
            "--pilot",
            "animal-octopus-arms",
            "--shots",
            "S01",
            "--width",
            "704",
            "--height",
            "1280",
            "--artifact-root",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["request_count"] == 1
    assert payload["canvas"] == {"width": 704, "height": 1280, "orientation": "portrait"}
    assert payload["requests"][0]["shot_id"] == "S01"
    assert payload["provider_calls_made"] == 0
    assert payload["publish_allowed"] is False
