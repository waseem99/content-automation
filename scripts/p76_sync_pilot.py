#!/usr/bin/env python3
"""Synchronize one local P68 pilot into a database-backed portfolio review item."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p76_portfolio_bridge import (  # noqa: E402
    artifact_already_registered,
    discover_artifacts,
    load_pilot_workspace,
    materialize_artifact,
    safe_media_relative,
    workspace_changed,
)


def api(base: str, key: str, path: str, payload: dict | None = None) -> dict:
    request = Request(
        f"{base.rstrip('/')}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json", "X-Operator-Key": key},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
    if body.get("ok") is False:
        raise RuntimeError(f"{path} failed: {body.get('error', 'unknown_error')}")
    return body


def resolve_content_id(base: str, key: str, content_id: str | None, match_title: str | None) -> str:
    if content_id:
        return content_id
    if not match_title:
        raise ValueError("Provide --content-id or --match-title")
    queue = api(base, key, "/portfolio/queue")["items"]
    matches = [str(item["id"]) for item in queue if str(item["title"]).casefold() == match_title.casefold()]
    if len(matches) != 1:
        raise ValueError(f"Expected one exact title match for {match_title!r}; found {len(matches)}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-id", required=True)
    parser.add_argument("--content-id")
    parser.add_argument("--match-title")
    parser.add_argument("--brand-slug", default="rawr-nation")
    parser.add_argument("--pilot-root", type=Path, default=Path("p68-pilots"))
    parser.add_argument("--artifact-root", type=Path, default=Path("p68-artifacts/gold"))
    parser.add_argument("--media-root", type=Path, default=Path(os.getenv("PORTFOLIO_MEDIA_ROOT", "var/portfolio-media")))
    parser.add_argument("--api-url", default=os.getenv("PORTFOLIO_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--skip-keyframes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--confirm-editorial-match",
        action="store_true",
        help="Confirm that the pilot topic and selected portfolio concept are the same editorial item.",
    )
    args = parser.parse_args()
    key = os.getenv("OPERATOR_KEY", "").strip()
    if not args.dry_run and not key:
        raise SystemExit("OPERATOR_KEY is required unless --dry-run is used")
    if not args.dry_run and not args.confirm_editorial_match:
        raise SystemExit("--confirm-editorial-match is required for a real synchronization")

    pilot_dir = args.pilot_root / args.pilot_id
    artifact_dir = args.artifact_root / args.pilot_id
    workspace = load_pilot_workspace(pilot_dir)
    candidates = discover_artifacts(artifact_dir, include_keyframes=not args.skip_keyframes)
    if not candidates:
        raise SystemExit(f"No review media found beneath {artifact_dir}")
    voice_candidate = next((candidate for candidate in candidates if candidate.kind == "voiceover"), None)
    if voice_candidate and voice_candidate.metadata.get("provider"):
        workspace["voiceover"]["provider"] = voice_candidate.metadata["provider"]

    if args.dry_run:
        content_id = args.content_id or "DRY-RUN-CONTENT-ID"
        payloads = []
        for candidate in candidates:
            relative = safe_media_relative(
                brand_slug=args.brand_slug, content_id=content_id, pilot_id=args.pilot_id, candidate=candidate
            )
            payloads.append(materialize_artifact(candidate, media_root=args.media_root, relative=relative, dry_run=True))
        print(json.dumps({"ok": True, "dry_run": True, "workspace": workspace, "artifacts": payloads}, indent=2))
        return 0

    content_id = resolve_content_id(args.api_url, key, args.content_id, args.match_title)
    detail = api(args.api_url, key, f"/portfolio/content/{content_id}")
    workspace_updated = False
    if workspace_changed(detail["item"], workspace):
        api(args.api_url, key, f"/portfolio/content/{content_id}/workspace", workspace)
        workspace_updated = True
        detail = api(args.api_url, key, f"/portfolio/content/{content_id}")

    registered, skipped = [], []
    for candidate in candidates:
        relative = safe_media_relative(
            brand_slug=args.brand_slug, content_id=content_id, pilot_id=args.pilot_id, candidate=candidate
        )
        payload = materialize_artifact(candidate, media_root=args.media_root, relative=relative)
        if artifact_already_registered(detail.get("artifacts", []), payload):
            skipped.append(payload["local_locator"])
            continue
        result = api(args.api_url, key, f"/portfolio/content/{content_id}/artifacts", payload)
        registered.append(result["artifact"]["id"])
        detail.setdefault("artifacts", []).append(result["artifact"])
    print(json.dumps({
        "ok": True, "content_id": content_id, "pilot_id": args.pilot_id,
        "workspace_updated": workspace_updated, "registered_count": len(registered),
        "skipped_existing_count": len(skipped), "registered_artifact_ids": registered,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
