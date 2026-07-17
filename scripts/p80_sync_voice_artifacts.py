#!/usr/bin/env python3
"""Copy Rawr narration previews into local review media and register them in PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path


def api(base: str, key: str, method: str, path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Content-Type": "application/json", "X-Operator-Key": key},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - explicit loopback API
        result = json.loads(response.read().decode())
    if result.get("ok") is False:
        raise RuntimeError(f"{path}: {result.get('error', 'unknown_error')}")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio", type=Path, default=Path("web/static-creator-ui/data/rawr-nation-month-studio.json"))
    parser.add_argument("--source", type=Path, default=Path("video-engine/public/generated"))
    parser.add_argument("--media-root", type=Path, default=Path("var/portfolio-media"))
    parser.add_argument("--api", default=os.getenv("OPERATOR_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--key", default=os.getenv("OPERATOR_KEY", ""))
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    if not args.key:
        raise SystemExit("OPERATOR_KEY is required")

    studio = json.loads(args.studio.read_text(encoding="utf-8"))
    queue = api(args.api, args.key, "GET", "/portfolio/queue")["items"]
    brand_slug = studio["brand"]["slug"]
    by_title = {item["title"]: item for item in queue if item.get("brand_slug") == brand_slug}
    registered, skipped, missing = [], [], []

    for package in studio["items"][: args.limit]:
        target = by_title.get(package["title"])
        source = args.source / f"{package['id']}-kokoro.wav"
        if not target or not source.is_file() or source.stat().st_size < 1024:
            missing.append(package["title"])
            continue
        relative = Path(brand_slug) / str(target["id"]) / "voice" / source.name
        destination = args.media_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = sha256(destination)
        detail = api(args.api, args.key, "GET", f"/portfolio/content/{target['id']}")
        locator = f"content://{relative.as_posix()}"
        if any(item.get("local_locator") == locator and item.get("sha256") == digest for item in detail.get("artifacts", [])):
            skipped.append(locator)
            continue
        result = api(
            args.api,
            args.key,
            "POST",
            f"/portfolio/content/{target['id']}/artifacts",
            {
                "kind": "voiceover",
                "label": "Kokoro narration preview",
                "local_locator": locator,
                "mime_type": "audio/wav",
                "sha256": digest,
                "size_bytes": destination.stat().st_size,
                "metadata": {"provider": "kokoro_local", "review_required": True, "source": "p82_portfolio_batch_one", "brand_slug": brand_slug},
            },
        )
        registered.append(str(result["artifact"]["id"]))

    print(json.dumps({"registered": registered, "skipped": skipped, "missing": missing}, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
