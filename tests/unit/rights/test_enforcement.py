from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.rights.decision_models import RightsGateDecision
from src.application.rights.enforcement import ManifestAdmissionGuard, RenderStartGuard
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.exceptions import RightsGateBlocked, RightsReviewRequired
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest


class FakeGate:
    def __init__(self, outcome: RightsDecisionOutcome) -> None:
        self.outcome = outcome
        self.points: list[RightsGatePoint] = []

    def evaluate(self, request: RightsGateRequest) -> RightsGateDecision:
        self.points.append(request.gate_point)
        reasons = ()
        if self.outcome == RightsDecisionOutcome.BLOCK:
            reasons = (RightsReasonCode.RIGHTS_NOT_APPROVED,)
        elif self.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED:
            reasons = (RightsReasonCode.RIGHTS_REVIEW_DUE,)
        return RightsGateDecision(
            evaluation_id=uuid4(),
            outcome=self.outcome,
            asset_decisions=(),
            reason_codes=reasons,
            policy_version="1.0.0",
            policy_hash="a" * 64,
            evaluated_at=datetime.now(timezone.utc),
        )


def _request() -> RightsGateRequest:
    return RightsGateRequest(
        workflow_run_id=uuid4(),
        gate_point=RightsGatePoint.MANUAL_CHECK,
        asset_ids=(uuid4(),),
        platform=RightsPlatform.YOUTUBE,
        territory="US",
        evaluated_by="pytest",
    )


def test_blocked_admission_does_not_call_manifest_callback() -> None:
    called = False

    def callback():
        nonlocal called
        called = True

    guard = ManifestAdmissionGuard(FakeGate(RightsDecisionOutcome.BLOCK))
    with pytest.raises(RightsGateBlocked):
        guard.execute(_request(), callback)
    assert called is False


def test_review_required_does_not_advance() -> None:
    called = False

    def callback():
        nonlocal called
        called = True

    guard = ManifestAdmissionGuard(FakeGate(RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED))
    with pytest.raises(RightsReviewRequired):
        guard.execute(_request(), callback)
    assert called is False


def test_render_guard_revalidates_and_calls_only_on_pass() -> None:
    gate = FakeGate(RightsDecisionOutcome.PASS)
    guard = RenderStartGuard(gate)
    result = guard.execute(_request(), lambda: "rendered")
    assert result == "rendered"
    assert gate.points == [RightsGatePoint.RENDER_START]
