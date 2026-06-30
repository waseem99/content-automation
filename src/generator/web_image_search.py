"""Fetch images from the web via SerpAPI with copyright-safety filters."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

import httpx
from PIL import Image

from src.config import Settings
from src.generator.entity_matcher import image_result_matches_entity

SERPAPI_URL = "https://serpapi.com/search.json"


@dataclass
class ImageSearchResult:
    url: str
    title: str
    source: str
    domain: str
    width: int
    filter_pass: str


def _domain_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _haystack(result: dict) -> str:
    parts = [
        result.get("link", ""),
        result.get("title", ""),
        result.get("source", ""),
        result.get("original", ""),
    ]
    return " ".join(str(part) for part in parts).lower()


def is_safe_image_result(result: dict, settings: Settings) -> bool:
    haystack = _haystack(result)
    for keyword in settings.image_blocklist_keywords:
        if keyword.lower() in haystack:
            return False

    for domain in settings.image_blocklist_domains:
        if domain.lower() in haystack:
            return False

    width = int(result.get("original_width") or result.get("width") or 0)
    if width and width < settings.image_min_width:
        return False

    url = result.get("original") or result.get("thumbnail") or result.get("link") or ""
    if not url:
        return False

    return True


def _prefer_score(result: dict, settings: Settings) -> int:
    haystack = _haystack(result)
    for index, domain in enumerate(settings.image_prefer_domains):
        if domain.lower() in haystack:
            return index
    return len(settings.image_prefer_domains)


def _parse_serpapi_results(payload: dict, filter_pass: str, settings: Settings) -> list[ImageSearchResult]:
    items = payload.get("images_results") or []
    candidates: list[ImageSearchResult] = []
    for item in items:
        if not is_safe_image_result(item, settings):
            continue
        url = item.get("original") or item.get("thumbnail") or item.get("link") or ""
        candidates.append(
            ImageSearchResult(
                url=url,
                title=str(item.get("title") or ""),
                source=str(item.get("source") or ""),
                domain=_domain_from_url(url),
                width=int(item.get("original_width") or item.get("width") or 0),
                filter_pass=filter_pass,
            )
        )

    candidates.sort(key=lambda candidate: _prefer_score({"link": candidate.url, "source": candidate.source}, settings))
    return candidates


def _get_with_retries(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float,
    max_retries: int,
    label: str,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt < max_retries:
                wait = min(2.0 * attempt, 8.0)
                print(
                    f"  {label} failed (attempt {attempt}/{max_retries}): {exc}. "
                    f"Retrying in {wait:.0f}s...",
                    flush=True,
                )
                time.sleep(wait)
    raise RuntimeError(f"{label} failed after {max_retries} attempts: {last_error}") from last_error


def _serpapi_search(params: dict, settings: Settings) -> dict:
    if not settings.serpapi_api_key:
        raise ValueError("SERPAPI_API_KEY is not set. Add it to your .env file.")

    query_params = {
        "engine": "google_images",
        "api_key": settings.serpapi_api_key,
        "num": 20,
        **params,
    }
    response = _get_with_retries(
        SERPAPI_URL,
        params=query_params,
        timeout=settings.serpapi_timeout_sec,
        max_retries=settings.serpapi_max_retries,
        label="SerpAPI search",
    )
    return response.json()


def search_images(
    query: str,
    settings: Settings,
    *,
    result_offset: int = 0,
    exclude_urls: set[str] | None = None,
    entity_name: str = "",
) -> list[ImageSearchResult]:
    exclude_urls = exclude_urls or set()
    passes: list[tuple[str, dict]] = [
        ("wikimedia", {"q": f"{query} site:commons.wikimedia.org", "tbs": "isz:l"}),
        ("cc", {"q": query, "tbs": f"{settings.image_license_filter},isz:l"}),
    ]

    seen_urls: set[str] = set(exclude_urls)
    results: list[ImageSearchResult] = []
    for filter_pass, params in passes:
        try:
            payload = _serpapi_search(params, settings)
        except Exception as exc:
            print(f"  SerpAPI pass '{filter_pass}' skipped: {exc}", flush=True)
            continue
        for candidate in _parse_serpapi_results(payload, filter_pass, settings):
            if candidate.url in seen_urls:
                continue
            if entity_name:
                haystack = f"{candidate.title} {candidate.source} {candidate.url}"
                if not image_result_matches_entity(haystack, entity_name):
                    continue
            seen_urls.add(candidate.url)
            results.append(candidate)

    if result_offset and results:
        rotated = results[result_offset % len(results) :] + results[: result_offset % len(results)]
        return rotated
    return results


def download_image(url: str, out_path: Path, settings: Settings) -> tuple[Path, int, int]:
    headers = {"User-Agent": "youtube-automation/1.0"}
    response = _get_with_retries(
        url,
        headers=headers,
        timeout=settings.image_download_timeout_sec,
        max_retries=settings.image_download_max_retries,
        label="Image download",
    )

    content_type = response.headers.get("content-type", "").lower()
    if content_type and "image" not in content_type and "octet-stream" not in content_type:
        raise ValueError(f"URL did not return an image: {content_type}")

    image = Image.open(BytesIO(response.content))
    width, height = image.size
    if width < settings.image_min_width:
        raise ValueError(f"Image too small: {width}x{height}")

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(image, mask=image.split()[3])
        image = background

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG")
    return out_path, width, height


def append_image_source_log(
    log_path: Path,
    entry: dict,
) -> None:
    entries: list[dict] = []
    if log_path.exists():
        entries = json.loads(log_path.read_text(encoding="utf-8"))
    entries.append(entry)
    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def search_and_download(
    query: str,
    out_path: Path,
    settings: Settings,
    segment_label: str,
    log_path: Path,
    *,
    result_offset: int = 0,
    exclude_urls: set[str] | None = None,
    entity_name: str = "",
) -> Path:
    if not query.strip():
        raise ValueError(f"Empty image search query for segment {segment_label}")

    candidates = search_images(
        query,
        settings,
        result_offset=result_offset,
        exclude_urls=exclude_urls,
        entity_name=entity_name,
    )
    if not candidates:
        raise RuntimeError(
            f"No copyright-filtered images found for '{query}'. "
            "Try a different topic query or place a manual PNG in production/ and use --skip-images."
        )

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            saved_path, width, height = download_image(candidate.url, out_path, settings)
            append_image_source_log(
                log_path,
                {
                    "segment": segment_label,
                    "query": query,
                    "url": candidate.url,
                    "domain": candidate.domain,
                    "title": candidate.title,
                    "filter_pass": candidate.filter_pass,
                    "width": width,
                    "height": height,
                },
            )
            return saved_path
        except Exception as exc:
            last_error = exc
            print(f"  Download skipped ({candidate.domain}): {exc}", flush=True)
            continue

    if last_error:
        raise RuntimeError(f"Failed to download any image for '{query}': {last_error}") from last_error
    raise RuntimeError(f"Failed to download any image for '{query}'")
