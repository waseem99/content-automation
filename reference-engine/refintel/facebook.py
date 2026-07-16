from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .adapters import canonicalize_url, normalize_reference

FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com"}
DIRECT_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_facebook_page_url(url: str) -> str:
    parsed = urlparse(url.strip())
    valid_host = (parsed.hostname or "").lower() in FACEBOOK_HOSTS
    if parsed.scheme not in {"http", "https"} or not valid_host:
        raise ValueError("A canonical facebook.com page URL is required")
    if "/share/" in parsed.path.lower():
        raise ValueError("Use a stable Facebook page ID or handle URL, not a share redirect")
    return url.strip()


def validate_facebook_share_url(url: str) -> str:
    parsed = urlparse(url.strip())
    valid_host = (parsed.hostname or "").lower() in FACEBOOK_HOSTS
    if parsed.scheme not in {"http", "https"} or not valid_host:
        raise ValueError("A facebook.com share URL is required")
    if not parsed.path.lower().startswith("/share/"):
        raise ValueError("The Facebook URL is not a share redirect")
    return canonicalize_url(url)


def resolve_facebook_share_url(
    url: str,
    *,
    profile_dir: Path,
    headless: bool = True,
    navigation_resolver: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Resolve an authorized Facebook share redirect using the dedicated local profile."""
    canonical_share = validate_facebook_share_url(url)
    if navigation_resolver:
        final_url = navigation_resolver(url)
    else:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Install the browser extra and run: playwright install chromium"
            ) from exc
        profile_dir = profile_dir.expanduser().resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(1500)
            final_url = page.url
            context.close()
    if "/share/" in urlparse(final_url).path.lower():
        raise RuntimeError(
            "Facebook did not resolve the share link. Open facebook-login and retry, "
            "or provide the stable page/reel URL."
        )
    canonical_media = canonical_video_url(final_url)
    resolved_url = canonical_media or canonicalize_url(final_url)
    normalized = normalize_reference(resolved_url)
    return {
        "schema_version": "p75.facebook_share_resolution.v1",
        "share_url": canonical_share,
        "resolved_url": resolved_url,
        "input_type": normalized.input_type.value,
        "platform": normalized.platform.value,
        "media_kind": normalized.media_kind.value,
        "requires_resolution": normalized.requires_resolution,
        "authentication": "authorized_local_browser",
    }


def canonical_video_url(url: str) -> str | None:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in FACEBOOK_HOSTS:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("reel", "reels", "videos"):
        indexes = [index for index, part in enumerate(parts) if part.lower() == marker]
        if not indexes:
            continue
        index = indexes[-1]
        if index + 1 >= len(parts) or not DIRECT_ID.fullmatch(parts[index + 1]):
            continue
        start = index - 1 if marker == "videos" and index > 0 else index
        canonical_path = "/" + "/".join(parts[start : index + 2])
        return urlunparse(("https", "www.facebook.com", canonical_path, "", "", ""))
    query = parse_qs(parsed.query)
    video_id = (query.get("v") or [None])[0]
    if parsed.path.rstrip("/").lower() == "/watch" and video_id:
        return f"https://www.facebook.com/watch?{urlencode({'v': video_id})}"
    return None


def page_discovery_urls(page_url: str) -> list[str]:
    page_url = validate_facebook_page_url(page_url)
    parsed = urlparse(page_url)
    query = parse_qs(parsed.query)
    page_id = (query.get("id") or [None])[0]
    if parsed.path.rstrip("/").lower() == "/profile.php" and page_id:
        return [
            f"https://www.facebook.com/profile.php?id={page_id}",
            f"https://www.facebook.com/profile.php?id={page_id}&sk=reels_tab",
            f"https://www.facebook.com/profile.php?id={page_id}&sk=videos",
        ]
    base = f"https://www.facebook.com{parsed.path.rstrip('/')}"
    return [base, f"{base}/reels", f"{base}/videos"]


def export_netscape_cookies(context: Any, target: Path) -> Path:
    """Export the current operator-owned browser context for local yt-dlp use."""
    lines = ["# Netscape HTTP Cookie File", "# Generated locally by refintel; do not share.", ""]
    for cookie in context.cookies("https://www.facebook.com"):
        domain = str(cookie.get("domain") or ".facebook.com")
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(cookie.get("path") or "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        # Netscape cookie jars use 0 for session cookies. Playwright may expose
        # -1, which yt-dlp rejects as an invalid expiry.
        expires = max(int(float(cookie.get("expires") or 0)), 0)
        name = str(cookie.get("name") or "").replace("\t", "")
        value = str(cookie.get("value") or "").replace("\t", "")
        if name:
            lines.append(
                "\t".join((domain, include_subdomains, path, secure, str(expires), name, value))
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def open_facebook_session(profile_dir: Path, *, wait_for_operator: bool = True) -> Path:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Install the browser extra and run: playwright install chromium"
        ) from exc
    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=90_000)
        if wait_for_operator:
            input("Log in to the authorized Facebook account in Chromium, then press Enter here: ")
        cookie_file = export_netscape_cookies(context, profile_dir / "facebook-cookies.txt")
        context.close()
    return cookie_file


def discover_facebook_videos(
    page_url: str,
    *,
    profile_dir: Path,
    limit: int = 12,
    headless: bool = True,
    scroll_rounds: int = 8,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Install the browser extra and run: playwright install chromium"
        ) from exc
    if limit < 1:
        raise ValueError("limit must be at least 1")
    targets = page_discovery_urls(page_url)
    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    found: dict[str, dict[str, Any]] = {}
    inspected: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else context.new_page()
        for target in targets:
            page.goto(target, wait_until="domcontentloaded", timeout=90_000)
            for _ in range(scroll_rounds):
                hrefs = page.locator("a[href]").evaluate_all(
                    "elements => elements.map(element => element.href)"
                )
                for href in hrefs:
                    canonical = canonical_video_url(str(href))
                    if canonical and canonical not in found:
                        found[canonical] = {"url": canonical, "discovered_on": target}
                if len(found) >= limit:
                    break
                page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 1.5, 900))")
                page.wait_for_timeout(900)
            inspected.append({"url": target, "title": page.title(), "final_url": page.url})
            if len(found) >= limit:
                break
        login_required = any("/login" in item["final_url"] for item in inspected) or bool(
            page.locator('input[name="email"]').count()
        )
        cookie_file = export_netscape_cookies(context, profile_dir / "facebook-cookies.txt")
        context.close()
    entries = list(found.values())[:limit]
    return {
        "schema_version": "p74.facebook_discovery.v1",
        "page_url": page_url,
        "generated_at": datetime.now(UTC).isoformat(),
        "login_required": login_required,
        "inspected": inspected,
        "entry_count": len(entries),
        "entries": entries,
        "cookie_file": str(cookie_file),
    }


def save_discovery(payload: dict[str, Any], target: Path) -> Path:
    sanitized = {key: value for key, value in payload.items() if key != "cookie_file"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sanitized, indent=2), encoding="utf-8")
    return target


def run_facebook_page_batch(
    page_url: str,
    *,
    brand: str,
    rights: Any,
    workspace_root: Path,
    profile_dir: Path,
    limit: int = 12,
    headless: bool = True,
    discover_only: bool = False,
    acquire_only: bool = False,
    use_local_vision: bool = True,
    transcription_model: str = "small",
    transcription_device: str = "auto",
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Discover, download, and analyze authorized videos from one Facebook page."""
    from .ingest import has_valid_cached_acquisition
    from .pipeline import ReferencePipeline

    discovery = discover_facebook_videos(
        page_url,
        profile_dir=profile_dir,
        limit=limit,
        headless=headless,
    )
    safe_brand = re.sub(r"[^a-z0-9-]+", "-", brand.lower()).strip("-")
    run_id = f"{safe_brand}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    run_dir = workspace_root.expanduser().resolve() / "page-runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    save_discovery(discovery, run_dir / "discovery.json")
    results: list[dict[str, Any]] = []
    emit = progress or (lambda _message: None)
    emit(f"Discovered {discovery['entry_count']} Facebook video references.")
    if not discover_only:
        pipeline = ReferencePipeline(workspace_root)
        for index, entry in enumerate(discovery["entries"], start=1):
            result: dict[str, Any] = {"index": index, "url": entry["url"]}
            try:
                emit(f"[{index}/{discovery['entry_count']}] Verifying acquisition.")
                project = pipeline.ingest_url(
                    entry["url"],
                    rights=rights,
                    title=f"{brand} reference {index:02d}",
                    operator_note=(
                        "Authorized page-level reference analysis. Source-specific assets must "
                        "not be copied into generated content."
                    ),
                    cookie_file=discovery["cookie_file"],
                )
                if not has_valid_cached_acquisition(project):
                    raise RuntimeError(
                        "Facebook acquisition did not produce verified primary media bytes."
                    )
                result["verified_acquisition"] = True
                emit(f"[{index}/{discovery['entry_count']}] Media bytes verified.")
                if acquire_only:
                    acquisition_manifest = (
                        Path(project.workspace_path)
                        / "source"
                        / "acquisition-manifest.json"
                    )
                    if project.status.value != "ingested" or not acquisition_manifest.is_file():
                        raise RuntimeError(
                            "Acquisition did not produce a verified ingested video project."
                        )
                    result.update(
                        {
                            "status": "acquired",
                            "reference_id": project.reference_id,
                            "acquisition_manifest": (
                                str(acquisition_manifest)
                                if acquisition_manifest.is_file()
                                else None
                            ),
                        }
                    )
                    results.append(result)
                    continue
                emit(
                    f"[{index}/{discovery['entry_count']}] Starting frame and "
                    f"{transcription_model} transcription analysis on {transcription_device}."
                )
                processed = pipeline.process(
                    project.reference_id,
                    transcription_model=transcription_model,
                    transcription_device=transcription_device,
                    use_local_vision=use_local_vision,
                    every_frame=True,
                )
                reference_workspace = Path(processed.workspace_path)
                if processed.media is None:
                    raise RuntimeError(
                        "Video analysis produced no media evidence. The cached acquisition is "
                        "failed or incomplete; rerun acquisition in a clean workspace."
                    )
                artifact_dir = run_dir / "analysis" / project.reference_id
                artifact_dir.mkdir(parents=True, exist_ok=True)
                copied: list[str] = []
                for relative in (
                    "analysis/reference_analysis.json",
                    "frames/every_frame_metrics.json",
                    "frames/frame_manifest.json",
                    "frames/contact_sheet.jpg",
                    "transcript/transcript.json",
                    "transcript/transcript.txt",
                    "exports/reference_fingerprint.json",
                    "reports/index.html",
                ):
                    source = reference_workspace / relative
                    if source.is_file():
                        target = artifact_dir / Path(relative).name
                        shutil.copy2(source, target)
                        copied.append(str(target.relative_to(run_dir)))
                required_evidence = {
                    "reference_analysis.json", "every_frame_metrics.json",
                    "frame_manifest.json", "reference_fingerprint.json", "index.html",
                }
                copied_names = {Path(item).name for item in copied}
                if not required_evidence.issubset(copied_names):
                    missing = sorted(required_evidence - copied_names)
                    raise RuntimeError(
                        "Video analysis evidence is incomplete; missing: " + ", ".join(missing)
                    )
                result.update(
                    {
                        "status": "analyzed",
                        "reference_id": processed.reference_id,
                        "duration_seconds": (
                            processed.media.duration_seconds if processed.media else None
                        ),
                        "decoded_frame_count": _decoded_frame_count(reference_workspace),
                        "scene_count": len(processed.scenes),
                        "transcript_segment_count": len(processed.transcript),
                        "artifacts": copied,
                    }
                )
                emit(f"[{index}/{discovery['entry_count']}] Analysis evidence complete.")
            except Exception as exc:  # noqa: BLE001 - record per-video failure and continue
                sanitized_error = str(exc).replace("\n", " ")[:1200]
                sanitized_error = sanitized_error.replace(
                    str(profile_dir.expanduser().resolve()), "<browser-profile>"
                ).replace(str(discovery["cookie_file"]), "<cookie-file>")
                result.update(
                    {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": sanitized_error,
                    }
                )
                emit(
                    f"[{index}/{discovery['entry_count']}] Failed: "
                    f"{type(exc).__name__}: {sanitized_error}"
                )
            results.append(result)
    payload = {
        "schema_version": "p74.facebook_page_batch.v1",
        "run_id": run_id,
        "brand": brand,
        "page_url": page_url,
        "rights_declaration": getattr(rights, "value", str(rights)),
        "discover_only": discover_only,
        "acquire_only": acquire_only,
        "entry_count": discovery["entry_count"],
        "summary": {
            "attempted": len(results),
            "verified_media": sum(
                bool(item.get("verified_acquisition")) for item in results
            ),
            "acquired": sum(item["status"] == "acquired" for item in results),
            "analyzed": sum(item["status"] == "analyzed" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
        },
        "results": results,
        "security": {
            "cookie_path_persisted_in_manifest": False,
            "browser_profile_outside_repository_recommended": True,
        },
    }
    (run_dir / "batch-result.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    payload["run_dir"] = str(run_dir)
    return payload


def _decoded_frame_count(workspace: Path) -> int:
    target = workspace / "frames" / "every_frame_metrics.json"
    if not target.is_file():
        return 0
    return int(json.loads(target.read_text(encoding="utf-8")).get("frame_count") or 0)
