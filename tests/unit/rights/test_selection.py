from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.match_footage import MatchFootageClassifier
from src.application.rights.policy import load_rights_policy
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
from src.application.rights.selection import EffectiveRightsSelector
from src.domain.asset_enums import AssetType
from src.domain.asset_models import Asset
from src.domain.asset_status import ApprovalStatus, AssetLifecycleStatus, AssetSourceType
from src.domain.rights_models import AssetRights


NOW = datetime(2026, 7, 5, tzinfo=timezone.utc)
POLICY = load_rights_policy(__import__("pathlib").Path("policies/rights-gate/v1.json"))


def _asset(*, metadata: dict | None = None) -> Asset:
    return Asset(
        id=uuid4(),
        asset_type=AssetType.VIDEO,
        source_type=AssetSourceType.CLIENT_SUPPLIED,
        lifecycle_status=AssetLifecycleStatus.INTERNAL_ONLY,
        storage_uri="workspace:///data/input/match.mp4",
        sha256="a" * 64,
        metadata=metadata or {},
        created_at=NOW,
        updated_at=NOW,
    )


def _rights(
    asset_id: UUID,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    platforms: list[str] | None = None,
    territories: list[str] | None = None,
    campaigns: list[str] | None = None,
    commercial: bool = True,
    editorial: bool = True,
    modification: bool = True,
    synthetic: bool = True,
    attribution_required: bool = False,
    attribution_text: str | None = None,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
    review_due_at: datetime | None = None,
) -> AssetRights:
    return AssetRights(
        id=uuid4(),
        asset_id=asset_id,
        rights_basis=AssetSourceType.LICENSED,
        commercial_use_allowed=commercial,
        editorial_use_allowed=editorial,
        modification_allowed=modification,
        synthetic_edit_allowed=synthetic,
        attribution_required=attribution_required,
        attribution_text=attribution_text,
        platforms=platforms if platforms is not None else ["youtube"],
        territories=territories if territories is not None else ["worldwide"],
        campaigns=campaigns or [],
        valid_from=valid_from,
        expires_at=expires_at,
        review_due_at=review_due_at,
        approval_status=status,
        approved_by="reviewer" if status == ApprovalStatus.APPROVED else None,
        approved_at=NOW if status == ApprovalStatus.APPROVED else None,
        created_at=NOW,
        updated_at=NOW,
    )


def _request(asset_id: UUID, **updates) -> RightsGateRequest:
    values = {
        "workflow_run_id": uuid4(),
        "gate_point": RightsGatePoint.MANIFEST_ADMISSION,
        "asset_ids": (asset_id,),
        "platform": RightsPlatform.YOUTUBE,
        "territory": "US",
        "commercial_use": True,
        "modification": True,
        "evaluated_by": "pytest",
    }
    values.update(updates)
    return RightsGateRequest(**values)


def _select(asset: Asset, records: list[AssetRights], request: RightsGateRequest, evidence=True):
    evidence_map = {
        record.id: ((uuid4(),) if evidence else ())
        for record in records
    }
    return EffectiveRightsSelector(POLICY).select(
        asset=asset,
        records=records,
        evidence_by_rights=evidence_map,
        request=request,
        now=NOW,
        is_match_footage=MatchFootageClassifier.is_match_footage(asset),
    )


def test_empty_platform_scope_does_not_allow_all_platforms() -> None:
    asset = _asset()
    decision = _select(asset, [_rights(asset.id, platforms=[])], _request(asset.id))
    assert decision.outcome == RightsDecisionOutcome.BLOCK
    assert RightsReasonCode.PLATFORM_NOT_ALLOWED in decision.reason_codes


def test_worldwide_scope_permits_country_code() -> None:
    asset = _asset()
    decision = _select(asset, [_rights(asset.id)], _request(asset.id))
    assert decision.outcome == RightsDecisionOutcome.PASS


def test_expired_and_revoked_rights_cannot_pass() -> None:
    asset = _asset()
    expired = _rights(asset.id, expires_at=NOW - timedelta(seconds=1))
    revoked = _rights(asset.id, status=ApprovalStatus.REVOKED)
    expired_decision = _select(asset, [expired], _request(asset.id))
    revoked_decision = _select(asset, [revoked], _request(asset.id))
    assert RightsReasonCode.RIGHTS_EXPIRED in expired_decision.reason_codes
    assert RightsReasonCode.RIGHTS_REVOKED in revoked_decision.reason_codes


def test_future_rights_and_missing_evidence_fail_closed() -> None:
    asset = _asset()
    future = _rights(asset.id, valid_from=NOW + timedelta(days=1))
    future_decision = _select(asset, [future], _request(asset.id))
    evidence_decision = _select(asset, [_rights(asset.id)], _request(asset.id), evidence=False)
    assert RightsReasonCode.RIGHTS_NOT_YET_VALID in future_decision.reason_codes
    assert RightsReasonCode.RIGHTS_EVIDENCE_MISSING in evidence_decision.reason_codes


def test_requested_permissions_are_independent() -> None:
    asset = _asset()
    rights = _rights(
        asset.id,
        commercial=False,
        editorial=False,
        modification=False,
        synthetic=False,
    )
    request = _request(
        asset.id,
        commercial_use=True,
        editorial_use=True,
        modification=True,
        synthetic_edit=True,
    )
    decision = _select(asset, [rights], request)
    assert set(decision.reason_codes) >= {
        RightsReasonCode.COMMERCIAL_USE_NOT_ALLOWED,
        RightsReasonCode.EDITORIAL_USE_NOT_ALLOWED,
        RightsReasonCode.MODIFICATION_NOT_ALLOWED,
        RightsReasonCode.SYNTHETIC_EDIT_NOT_ALLOWED,
    }


def test_attribution_is_returned_and_exactly_enforced() -> None:
    asset = _asset()
    rights = _rights(
        asset.id,
        attribution_required=True,
        attribution_text="Photo: Rights Holder",
    )
    missing = _select(asset, [rights], _request(asset.id))
    passing = _select(
        asset,
        [rights],
        _request(asset.id, supplied_attribution={asset.id: "Photo: Rights Holder"}),
    )
    assert RightsReasonCode.ATTRIBUTION_MISSING in missing.reason_codes
    assert passing.outcome == RightsDecisionOutcome.PASS
    assert passing.obligations.attribution_text == "Photo: Rights Holder"


def test_multiple_applicable_rights_require_human_review() -> None:
    asset = _asset()
    decision = _select(
        asset,
        [_rights(asset.id), _rights(asset.id)],
        _request(asset.id),
    )
    assert decision.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED
    assert decision.reason_codes == (RightsReasonCode.MULTIPLE_APPLICABLE_RIGHTS,)


def test_match_footage_uses_specific_block_reason() -> None:
    asset = _asset(metadata={"pipeline_role": "extracted_match_clip"})
    decision = _select(asset, [], _request(asset.id))
    assert decision.outcome == RightsDecisionOutcome.BLOCK
    assert decision.reason_codes[0] == RightsReasonCode.UNAPPROVED_MATCH_FOOTAGE


def test_reason_order_is_stable() -> None:
    asset = _asset()
    rights = _rights(asset.id, platforms=[], territories=[])
    first = _select(asset, [rights], _request(asset.id))
    second = _select(asset, [rights], _request(asset.id))
    assert first.reason_codes == second.reason_codes
