from src.application.campaigns.models import (
    ALLOWED_PLATFORMS,
    AutopilotPolicyCreateRequest,
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
    CampaignItemState,
    CampaignStatus,
    CampaignVersionStatus,
)
from src.application.campaigns.service import CampaignError
from src.application.campaigns.validated_service import ValidatedCampaignService

CampaignService = ValidatedCampaignService

__all__ = [
    "ALLOWED_PLATFORMS",
    "AutopilotPolicyCreateRequest",
    "CampaignCreateRequest",
    "CampaignError",
    "CampaignItemInput",
    "CampaignItemsAddRequest",
    "CampaignItemState",
    "CampaignService",
    "CampaignStatus",
    "CampaignVersionStatus",
    "ValidatedCampaignService",
]
