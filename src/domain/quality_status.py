from enum import StrEnum


class QualityOutcome(StrEnum):
    PASS = "pass"
    PASS_WITH_DISCLOSURE = "pass_with_disclosure"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
