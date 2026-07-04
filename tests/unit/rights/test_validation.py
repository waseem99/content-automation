from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.rights.exceptions import RightsApprovalError
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.validation import validate_rights_scopes
from src.domain.asset_status import ApprovalStatus, AssetSourceType
from src.domain.rights_models import AssetRights


NOW = datetime.now(timezone.utc)


def _rights(*, platforms: list[str], territories: list[str]) -> AssetRights:
    return AssetRights(
        id=uuid4(),
        asset_id=uuid4(),
        rights_basis=AssetSourceType.LICENSED,
        platforms=platforms,
        territories=territories,
        approval_status=ApprovalStatus.PENDING,
        created_at=NOW,
        updated_at=NOW,
    )


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(RightsApprovalError) as error:
        validate_rights_scopes(_rights(platforms=["unknown"], territories=["US"]))
    assert error.value.reason == RightsReasonCode.PLATFORM_NOT_ALLOWED


def test_invalid_territory_is_rejected() -> None:
    with pytest.raises(RightsApprovalError) as error:
        validate_rights_scopes(_rights(platforms=["youtube"], territories=["United States"]))
    assert error.value.reason == RightsReasonCode.TERRITORY_NOT_ALLOWED


def test_worldwide_and_iso_codes_are_accepted() -> None:
    validate_rights_scopes(
        _rights(platforms=["youtube", "instagram"], territories=["worldwide", "US"])
    )
