from __future__ import annotations

from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from .models import Platform


class SupportLevel(StrEnum):
    SUPPORTED = "supported"
    CONDITIONAL = "conditional"
    UNSUPPORTED = "unsupported"


class ReferenceInputType(StrEnum):
    DIRECT_MEDIA = "direct_media"
    PROFILE_PAGE = "profile_page"
    COLLECTION = "collection"
    SHARE_REDIRECT = "share_redirect"
    UNKNOWN = "unknown"


class MediaKind(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AcquisitionRoute(StrEnum):
    EXTRACTOR = "extractor"
    EXTRACTOR_THEN_BROWSER = "extractor_then_browser"
    DISCOVER_THEN_EXTRACT = "discover_then_extract"
    LOCAL_PLAYWRIGHT_DISCOVERY = "local_playwright_discovery"
    VERIFY_THEN_LOCAL_FILE = "verify_then_local_file"
    LOCAL_FILE = "local_file"
    UNSUPPORTED = "unsupported"


class AdapterCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    direct_video: SupportLevel
    image_or_carousel: SupportLevel
    profile_discovery: SupportLevel
    routes: list[AcquisitionRoute]
    authentication: str
    limitations: list[str] = Field(default_factory=list)


class NormalizedReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_url: str
    canonical_url: str
    platform: Platform
    input_type: ReferenceInputType
    media_kind: MediaKind
    support: SupportLevel
    route: AcquisitionRoute
    media_id: str | None = None
    requires_resolution: bool = False
    limitations: list[str] = Field(default_factory=list)


TRACKING_PARAMETERS = {
    "access_token",
    "auth",
    "authorization",
    "fbclid",
    "gclid",
    "igshid",
    "mibextid",
    "password",
    "secret",
    "si",
    "sig",
    "signature",
    "token",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

PLATFORM_HOSTS: tuple[tuple[str, Platform], ...] = (
    ("facebook.com", Platform.FACEBOOK),
    ("fb.watch", Platform.FACEBOOK),
    ("instagram.com", Platform.INSTAGRAM),
    ("youtube.com", Platform.YOUTUBE),
    ("youtu.be", Platform.YOUTUBE),
    ("tiktok.com", Platform.TIKTOK),
    ("twitter.com", Platform.X),
    ("x.com", Platform.X),
    ("snapchat.com", Platform.SNAPCHAT),
    ("drive.google.com", Platform.GOOGLE_DRIVE),
)


CAPABILITIES: dict[Platform, AdapterCapabilities] = {
    Platform.YOUTUBE: AdapterCapabilities(
        platform=Platform.YOUTUBE,
        direct_video=SupportLevel.SUPPORTED,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.CONDITIONAL,
        routes=[AcquisitionRoute.EXTRACTOR, AcquisitionRoute.DISCOVER_THEN_EXTRACT],
        authentication="Prefer public media or an authorized local export; do not automate login.",
        limitations=["Community images and channel enumeration require route verification."],
    ),
    Platform.INSTAGRAM: AdapterCapabilities(
        platform=Platform.INSTAGRAM,
        direct_video=SupportLevel.CONDITIONAL,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.CONDITIONAL,
        routes=[AcquisitionRoute.EXTRACTOR_THEN_BROWSER, AcquisitionRoute.DISCOVER_THEN_EXTRACT],
        authentication="Use only an operator-controlled local browser profile when authorized.",
        limitations=["Public routes can require login or change without notice."],
    ),
    Platform.TIKTOK: AdapterCapabilities(
        platform=Platform.TIKTOK,
        direct_video=SupportLevel.CONDITIONAL,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.CONDITIONAL,
        routes=[AcquisitionRoute.EXTRACTOR, AcquisitionRoute.DISCOVER_THEN_EXTRACT],
        authentication="Prefer public URLs; use an authorized local export after a challenge.",
        limitations=["Extractor and public-site behavior can drift."],
    ),
    Platform.X: AdapterCapabilities(
        platform=Platform.X,
        direct_video=SupportLevel.CONDITIONAL,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.CONDITIONAL,
        routes=[AcquisitionRoute.EXTRACTOR, AcquisitionRoute.DISCOVER_THEN_EXTRACT],
        authentication=(
            "Never collect credentials; local browser state must remain operator-controlled."
        ),
        limitations=["A status may contain multiple mixed media assets."],
    ),
    Platform.FACEBOOK: AdapterCapabilities(
        platform=Platform.FACEBOOK,
        direct_video=SupportLevel.CONDITIONAL,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.CONDITIONAL,
        routes=[AcquisitionRoute.EXTRACTOR, AcquisitionRoute.LOCAL_PLAYWRIGHT_DISCOVERY],
        authentication="The operator completes login in the dedicated local Playwright profile.",
        limitations=["Share links must be resolved before media classification."],
    ),
    Platform.SNAPCHAT: AdapterCapabilities(
        platform=Platform.SNAPCHAT,
        direct_video=SupportLevel.CONDITIONAL,
        image_or_carousel=SupportLevel.CONDITIONAL,
        profile_discovery=SupportLevel.UNSUPPORTED,
        routes=[AcquisitionRoute.VERIFY_THEN_LOCAL_FILE, AcquisitionRoute.LOCAL_FILE],
        authentication="Do not automate login; use a public link or authorized local export.",
        limitations=[
            "Spotlight and public Story routes are experimental and must be verified per URL."
        ],
    ),
}


def detect_platform(url: str) -> Platform:
    host = (urlsplit(url).hostname or "").lower()
    for known, platform in PLATFORM_HOSTS:
        if host == known or host.endswith(f".{known}"):
            return platform
    return Platform.UNKNOWN


def canonicalize_url(url: str) -> str:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Reference URL must be an absolute HTTP(S) URL")
    host = parsed.hostname.lower()
    if host == "twitter.com" or host.endswith(".twitter.com"):
        host = "x.com"
    if host.startswith("www."):
        host = host[4:]
    port = f":{parsed.port}" if parsed.port else ""
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(("https", host + port, path, query, ""))


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def normalize_reference(url: str) -> NormalizedReference:
    canonical = canonicalize_url(url)
    parsed = urlsplit(canonical)
    host = parsed.hostname or ""
    path = parsed.path.lower()
    parts = _path_parts(parsed.path)
    query = dict(parse_qsl(parsed.query))
    platform = detect_platform(canonical)
    input_type = ReferenceInputType.UNKNOWN
    media_kind = MediaKind.UNKNOWN
    support = SupportLevel.UNSUPPORTED
    route = AcquisitionRoute.UNSUPPORTED
    media_id: str | None = None
    requires_resolution = False
    limitations: list[str] = []

    if platform == Platform.YOUTUBE:
        if host == "youtu.be" and parts:
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.SUPPORTED,
                AcquisitionRoute.EXTRACTOR,
            )
            media_id = parts[0]
        elif path == "/watch" and query.get("v"):
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.SUPPORTED,
                AcquisitionRoute.EXTRACTOR,
            )
            media_id = query["v"]
        elif len(parts) >= 2 and parts[0].lower() in {"shorts", "live"}:
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.SUPPORTED,
                AcquisitionRoute.EXTRACTOR,
            )
            media_id = parts[1]
        else:
            input_type, support, route = (
                ReferenceInputType.COLLECTION,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.DISCOVER_THEN_EXTRACT,
            )
    elif platform == Platform.INSTAGRAM:
        if len(parts) >= 2 and parts[0].lower() in {"reel", "reels", "tv"}:
            input_type, media_kind, support, route, media_id = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR_THEN_BROWSER,
                parts[1],
            )
        elif len(parts) >= 2 and parts[0].lower() == "p":
            input_type, media_kind, support, route, media_id = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.MIXED,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR_THEN_BROWSER,
                parts[1],
            )
        else:
            input_type, support, route = (
                ReferenceInputType.PROFILE_PAGE,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.DISCOVER_THEN_EXTRACT,
            )
    elif platform == Platform.TIKTOK:
        lower_parts = [part.lower() for part in parts]
        marker = (
            "video"
            if "video" in lower_parts
            else "photo"
            if "photo" in lower_parts
            else None
        )
        if marker:
            index = lower_parts.index(marker)
            media_id = parts[index + 1] if len(parts) > index + 1 else None
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO if marker == "video" else MediaKind.CAROUSEL,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
            )
        else:
            input_type, support, route = (
                ReferenceInputType.PROFILE_PAGE,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.DISCOVER_THEN_EXTRACT,
            )
    elif platform == Platform.X:
        lower_parts = [part.lower() for part in parts]
        if "status" in lower_parts:
            index = lower_parts.index("status")
            media_id = parts[index + 1] if len(parts) > index + 1 else None
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.MIXED,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
            )
        else:
            input_type, support, route = (
                ReferenceInputType.PROFILE_PAGE,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.DISCOVER_THEN_EXTRACT,
            )
    elif platform == Platform.FACEBOOK:
        if path.startswith("/share/"):
            input_type, support, route = (
                ReferenceInputType.SHARE_REDIRECT,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.LOCAL_PLAYWRIGHT_DISCOVERY,
            )
            requires_resolution = True
            limitations.append(
                "Resolve the share redirect before deciding whether it is media or a page."
            )
        elif host == "fb.watch" and parts:
            input_type, media_kind, support, route, media_id = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
                parts[0],
            )
        elif path == "/watch" and query.get("v"):
            input_type, media_kind, support, route, media_id = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
                query["v"],
            )
        elif len(parts) >= 2 and parts[0].lower() == "reel":
            input_type, media_kind, support, route, media_id = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
                parts[1],
            )
        elif "videos" in [part.lower() for part in parts]:
            index = [part.lower() for part in parts].index("videos")
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.VIDEO,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.EXTRACTOR,
            )
            media_id = parts[index + 1] if len(parts) > index + 1 else None
        else:
            input_type, support, route = (
                ReferenceInputType.PROFILE_PAGE,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.LOCAL_PLAYWRIGHT_DISCOVERY,
            )
    elif platform == Platform.SNAPCHAT:
        lower_parts = [part.lower() for part in parts]
        marker = (
            "spotlight"
            if "spotlight" in lower_parts
            else "story"
            if "story" in lower_parts
            else None
        )
        if marker:
            index = lower_parts.index(marker)
            media_id = parts[index + 1] if len(parts) > index + 1 else None
            input_type, media_kind, support, route = (
                ReferenceInputType.DIRECT_MEDIA,
                MediaKind.MIXED,
                SupportLevel.CONDITIONAL,
                AcquisitionRoute.VERIFY_THEN_LOCAL_FILE,
            )
            limitations.append("Verify this public Snapchat link type before acquisition.")
        else:
            input_type, support, route = (
                ReferenceInputType.PROFILE_PAGE,
                SupportLevel.UNSUPPORTED,
                AcquisitionRoute.LOCAL_FILE,
            )
            limitations.append("Use an authorized local export for Snapchat profile/page inputs.")

    return NormalizedReference(
        original_url=url,
        canonical_url=canonical,
        platform=platform,
        input_type=input_type,
        media_kind=media_kind,
        support=support,
        route=route,
        media_id=media_id,
        requires_resolution=requires_resolution,
        limitations=limitations,
    )


def capability_matrix() -> list[AdapterCapabilities]:
    order = (
        Platform.FACEBOOK,
        Platform.YOUTUBE,
        Platform.INSTAGRAM,
        Platform.TIKTOK,
        Platform.X,
        Platform.SNAPCHAT,
    )
    return [CAPABILITIES[platform] for platform in order]


def resolve_adapter(url: str) -> AdapterCapabilities | None:
    return CAPABILITIES.get(detect_platform(url))
