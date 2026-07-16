#!/usr/bin/env python3
"""Read-only local readiness report for portfolio production."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    api_url = os.getenv("PORTFOLIO_API_URL", "http://127.0.0.1:8000").rstrip("/")
    media_root = Path(os.getenv("PORTFOLIO_MEDIA_ROOT", "var/portfolio-media"))
    checks = {
        "docker_available": shutil.which("docker") is not None,
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "operator_key_present": bool(os.getenv("OPERATOR_KEY", "").strip()),
        "media_root": str(media_root),
        "media_root_exists": media_root.is_dir(),
        "media_root_writable": media_root.is_dir() and os.access(media_root, os.W_OK),
        "rawr_pilot_workspace_present": Path("p68-pilots/rawr-blind-spot/content-plan.json").is_file(),
        "rawr_preview_present": Path("p68-artifacts/gold/rawr-blind-spot/renders/hybrid-v1/final_review.mp4").is_file(),
        "kokoro_narration_present": Path("p68-artifacts/gold/rawr-blind-spot/narration/rawr-blind-spot-kokoro.wav").is_file(),
        "comfyui_configured": bool(os.getenv("P68_KEYFRAME_BASE_URL", "").strip() or os.getenv("P68_RN_BASE_URL", "").strip()),
    }
    try:
        with urlopen(f"{api_url}/health", timeout=3) as response:
            checks["operator_api_reachable"] = response.status == 200
    except (URLError, TimeoutError):
        checks["operator_api_reachable"] = False
    required_now = (
        "docker_available", "ffmpeg_available", "operator_key_present", "media_root_exists",
        "media_root_writable", "rawr_pilot_workspace_present", "rawr_preview_present", "kokoro_narration_present",
    )
    blockers = [name for name in required_now if not checks[name]]
    print(json.dumps({
        "ok": not blockers,
        "checks": checks,
        "blockers": blockers,
        "optional_later": ["comfyui_configured"],
        "vercel_required": False,
        "paid_provider_required": False,
    }, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
