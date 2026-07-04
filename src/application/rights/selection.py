from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.rights.decision_models import (
    AssetRightsDecision,
    RightsObligations,
)
from src.application.rights.enums import RightsDecisionOutcome
from src.application.rights.policy import RightsPolicy
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
from src.domain.asset_models import Asset
from src.domain.asset_status import ApprovalStatus
from src.domain.rights_models import AssetRights


_BLOCKING_REASONS = {
    RightsReasonCode.RIGHTS_NOT_APPROVED,
    RightsReasonCode.RIGHTS_EVIDENCE_MISSING,
    RightsReasonCode.RIGHTS_EXPIRED,
    RightsReasonCode.RIGHTS_REVOKED,
    RightsReasonCode.RIGHTS_NOT_YET_VALID,
    RightsReasonCode.PLATFORM_NOT_ALLOWED,
    RightsReasonCode.TERRITORY_NOT_ALLOWED,
    RightsReasonCode.CAMPAIGN_NOT_ALLOWED,
    RightsReasonCode.COMMERCIAL_USE_NOT_ALLOWED,
    RightsReasonCode.EDITORIAL_USE_NOT_ALLOWED,
    RightsReasonCode.MODIFICATION_NOT_ALLOWED,
    RightsReasonCode.SYNTHETIC_EDIT_NOT_ALLOWED,
    RightsReasonCode.ATTRIBUTION_MISSING,
}


class EffectiveRightsSelector:
    def __init__(self, policy: RightsPolicy) -> None:
        self.policy = policy

    def select(
        self,
        *,
        asset: Asset,
        records: list[AssetRights],
        evidence_by_rights: dict[UUID, tuple[UUID, ...]],
        request: RightsGateRequest,
        now: datetime,
        is_match_footage: bool,
    ) -> AssetRightsDecision:
        passing: list[tuple[AssetRights, tuple[UUID, ...], RightsObligations, bool]] = []
        observed: set[RightsReasonCode] = set()

        for rights in records:
            reasons, obligations, review_due = self._evaluate_record(
                rights=rights,
                evidence_ids=evidence_by_rights.get(rights.id, ()),
                request=request,
                now=now,
            )
            observed.update(reasons)
            if not any(reason in _BLOCKING_REASONS for reason in reasons):
                passing.append(
                    (
                        rights,
                        evidence_by_rights.get(rights.id, ()),
                        obligations,
                        review_due,
                    )
                )

        if len(passing) > 1:
            reasons = self._ordered((RightsReasonCode.MULTIPLE_APPLICABLE_RIGHTS,))
            return AssetRightsDecision(
                asset_id=asset.id,
                asset_sha256=asset.sha256,
                outcome=RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED,
                reason_codes=reasons,
            )

        if len(passing) == 1:
            rights, evidence_ids, obligations, review_due = passing[0]
            if review_due:
                return AssetRightsDecision(
                    asset_id=asset.id,
                    asset_sha256=asset.sha256,
                    selected_rights_id=rights.id,
                    outcome=RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED,
                    reason_codes=self._ordered((RightsReasonCode.RIGHTS_REVIEW_DUE,)),
                    evidence_ids=evidence_ids,
                    obligations=obligations,
                )
            return AssetRightsDecision(
                asset_id=asset.id,
                asset_sha256=asset.sha256,
                selected_rights_id=rights.id,
                outcome=RightsDecisionOutcome.PASS,
                evidence_ids=evidence_ids,
                obligations=obligations,
            )

        if not observed:
            observed.add(RightsReasonCode.RIGHTS_NOT_APPROVED)
        if is_match_footage:
            observed.add(RightsReasonCode.UNAPPROVED_MATCH_FOOTAGE)
        return AssetRightsDecision(
            asset_id=asset.id,
            asset_sha256=asset.sha256,
            outcome=RightsDecisionOutcome.BLOCK,
            reason_codes=self._ordered(tuple(observed)),
        )

    def _evaluate_record(
        self,
        *,
        rights: AssetRights,
        evidence_ids: tuple[UUID, ...],
        request: RightsGateRequest,
        now: datetime,
    ) -> tuple[tuple[RightsReasonCode, ...], RightsObligations, bool]:
        reasons: set[RightsReasonCode] = set()

        if rights.approval_status == ApprovalStatus.REVOKED:
            reasons.add(RightsReasonCode.RIGHTS_REVOKED)
        elif rights.approval_status == ApprovalStatus.EXPIRED:
            reasons.add(RightsReasonCode.RIGHTS_EXPIRED)
        elif rights.approval_status != ApprovalStatus.APPROVED:
            reasons.add(RightsReasonCode.RIGHTS_NOT_APPROVED)

        if rights.valid_from is not None and rights.valid_from > now:
            reasons.add(RightsReasonCode.RIGHTS_NOT_YET_VALID)
        if rights.expires_at is not None and rights.expires_at <= now:
            reasons.add(RightsReasonCode.RIGHTS_EXPIRED)
        if not evidence_ids:
            reasons.add(RightsReasonCode.RIGHTS_EVIDENCE_MISSING)

        platforms = {item.strip().lower() for item in rights.platforms}
        if request.platform.value not in platforms:
            reasons.add(RightsReasonCode.PLATFORM_NOT_ALLOWED)

        territories = {
            item.strip().lower() if item.strip().lower() == "worldwide" else item.strip().upper()
            for item in rights.territories
        }
        if "worldwide" not in territories and request.territory not in territories:
            reasons.add(RightsReasonCode.TERRITORY_NOT_ALLOWED)

        campaigns = {item.strip().lower() for item in rights.campaigns if item.strip()}
        if campaigns and (request.campaign is None or request.campaign not in campaigns):
            reasons.add(RightsReasonCode.CAMPAIGN_NOT_ALLOWED)

        if request.commercial_use and not rights.commercial_use_allowed:
            reasons.add(RightsReasonCode.COMMERCIAL_USE_NOT_ALLOWED)
        if request.editorial_use and not rights.editorial_use_allowed:
            reasons.add(RightsReasonCode.EDITORIAL_USE_NOT_ALLOWED)
        if request.modification and not rights.modification_allowed:
            reasons.add(RightsReasonCode.MODIFICATION_NOT_ALLOWED)
        if request.synthetic_edit and not rights.synthetic_edit_allowed:
            reasons.add(RightsReasonCode.SYNTHETIC_EDIT_NOT_ALLOWED)

        required_text = (rights.attribution_text or "").strip()
        obligations = RightsObligations(
            attribution_required=rights.attribution_required,
            attribution_text=required_text or None,
        )
        if rights.attribution_required:
            supplied = request.supplied_attribution.get(rights.asset_id, "").strip()
            if not required_text or supplied != required_text:
                reasons.add(RightsReasonCode.ATTRIBUTION_MISSING)

        review_due = rights.review_due_at is not None and rights.review_due_at <= now
        if review_due:
            reasons.add(RightsReasonCode.RIGHTS_REVIEW_DUE)
        return self._ordered(tuple(reasons)), obligations, review_due

    def _ordered(
        self,
        reasons: tuple[RightsReasonCode, ...],
    ) -> tuple[RightsReasonCode, ...]:
        return tuple(
            sorted(
                set(reasons),
                key=lambda reason: (self.policy.priority(reason.value), reason.value),
            )
        )
