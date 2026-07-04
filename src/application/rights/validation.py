from __future__ import annotations

from src.application.rights.enums import RightsPlatform
from src.application.rights.exceptions import RightsApprovalError
from src.application.rights.reason_codes import RightsReasonCode
from src.domain.rights_models import AssetRights


def validate_rights_scopes(rights: AssetRights) -> None:
    supported = {item.value for item in RightsPlatform}
    platforms = {item.strip().lower() for item in rights.platforms}
    unknown = sorted(platforms - supported)
    if unknown:
        raise RightsApprovalError(
            RightsReasonCode.PLATFORM_NOT_ALLOWED,
            f"Unsupported platform values: {', '.join(unknown)}",
        )

    for territory in rights.territories:
        value = territory.strip()
        if value.lower() == "worldwide":
            continue
        if len(value) != 2 or not value.isalpha():
            raise RightsApprovalError(
                RightsReasonCode.TERRITORY_NOT_ALLOWED,
                f"Invalid territory value: {territory}",
            )
