from __future__ import annotations

import pytest

from refintel.adapters import (
    AcquisitionRoute,
    MediaKind,
    ReferenceInputType,
    SupportLevel,
    canonicalize_url,
    capability_matrix,
    normalize_reference,
)
from refintel.ingest import canonical_url_key, validate_direct_video_url
from refintel.models import Platform


@pytest.mark.parametrize(
    ("url", "platform", "input_type", "media_kind", "route"),
    [
        (
            "https://www.youtube.com/shorts/abc?si=tracking",
            Platform.YOUTUBE,
            ReferenceInputType.DIRECT_MEDIA,
            MediaKind.VIDEO,
            AcquisitionRoute.EXTRACTOR,
        ),
        (
            "https://www.instagram.com/p/post-id/",
            Platform.INSTAGRAM,
            ReferenceInputType.DIRECT_MEDIA,
            MediaKind.MIXED,
            AcquisitionRoute.EXTRACTOR_THEN_BROWSER,
        ),
        (
            "https://www.tiktok.com/@creator/photo/123",
            Platform.TIKTOK,
            ReferenceInputType.DIRECT_MEDIA,
            MediaKind.CAROUSEL,
            AcquisitionRoute.EXTRACTOR,
        ),
        (
            "https://twitter.com/creator/status/456?utm_source=test",
            Platform.X,
            ReferenceInputType.DIRECT_MEDIA,
            MediaKind.MIXED,
            AcquisitionRoute.EXTRACTOR,
        ),
        (
            "https://www.facebook.com/RawrNationTV",
            Platform.FACEBOOK,
            ReferenceInputType.PROFILE_PAGE,
            MediaKind.UNKNOWN,
            AcquisitionRoute.LOCAL_PLAYWRIGHT_DISCOVERY,
        ),
        (
            "https://www.snapchat.com/spotlight/example-id",
            Platform.SNAPCHAT,
            ReferenceInputType.DIRECT_MEDIA,
            MediaKind.MIXED,
            AcquisitionRoute.VERIFY_THEN_LOCAL_FILE,
        ),
    ],
)
def test_normalized_reference_contract(
    url: str,
    platform: Platform,
    input_type: ReferenceInputType,
    media_kind: MediaKind,
    route: AcquisitionRoute,
) -> None:
    reference = normalize_reference(url)
    assert reference.platform == platform
    assert reference.input_type == input_type
    assert reference.media_kind == media_kind
    assert reference.route == route


def test_canonicalization_removes_tracking_and_normalizes_twitter_host() -> None:
    result = canonicalize_url(
        "https://www.twitter.com/creator/status/123/?utm_source=test&keep=yes#fragment"
    )
    assert result == "https://x.com/creator/status/123?keep=yes"


def test_youtube_watch_identity_preserves_video_id() -> None:
    first = canonical_url_key("https://www.youtube.com/watch?v=first&utm_source=test")
    second = canonical_url_key("https://youtube.com/watch?v=second")
    assert first == "url:https://youtube.com/watch?v=first"
    assert second == "url:https://youtube.com/watch?v=second"
    assert first != second


def test_facebook_share_link_requires_resolution_before_ingestion() -> None:
    reference = normalize_reference(
        "https://www.facebook.com/share/1F6ytSUb6X/?mibextid=wwXIfr"
    )
    assert reference.input_type == ReferenceInputType.SHARE_REDIRECT
    assert reference.requires_resolution is True
    with pytest.raises(ValueError, match="resolved"):
        validate_direct_video_url(reference.original_url)


def test_snapchat_support_is_conditional_and_profile_falls_back_to_local_file() -> None:
    spotlight = normalize_reference("https://snapchat.com/spotlight/example")
    profile = normalize_reference("https://snapchat.com/add/example")
    assert spotlight.support == SupportLevel.CONDITIONAL
    assert validate_direct_video_url(spotlight.original_url) == Platform.SNAPCHAT
    assert profile.support == SupportLevel.UNSUPPORTED
    assert profile.route == AcquisitionRoute.LOCAL_FILE


def test_capability_matrix_is_complete_and_never_overstates_profile_discovery() -> None:
    matrix = capability_matrix()
    assert {row.platform for row in matrix} == {
        Platform.FACEBOOK,
        Platform.YOUTUBE,
        Platform.INSTAGRAM,
        Platform.TIKTOK,
        Platform.X,
        Platform.SNAPCHAT,
    }
    assert all(row.profile_discovery != SupportLevel.SUPPORTED for row in matrix)
    snapchat = next(row for row in matrix if row.platform == Platform.SNAPCHAT)
    assert snapchat.profile_discovery == SupportLevel.UNSUPPORTED
