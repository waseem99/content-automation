from enum import StrEnum


class RightsDecisionOutcome(StrEnum):
    PASS = "pass"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    BLOCK = "block"


class RightsGatePoint(StrEnum):
    MANIFEST_ADMISSION = "manifest_admission"
    RENDER_START = "render_start"
    MANUAL_CHECK = "manual_check"


class RightsPlatform(StrEnum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
