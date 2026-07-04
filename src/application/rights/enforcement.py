from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint
from src.application.rights.exceptions import RightsGateBlocked, RightsReviewRequired
from src.application.rights.gate import RightsGateService
from src.application.rights.request_models import RightsGateRequest


ResultT = TypeVar("ResultT")


class ManifestAdmissionGuard:
    def __init__(self, gate: RightsGateService) -> None:
        self.gate = gate

    def authorize(self, request: RightsGateRequest):
        request = request.model_copy(update={"gate_point": RightsGatePoint.MANIFEST_ADMISSION})
        return self.gate.evaluate(request)

    def execute(
        self,
        request: RightsGateRequest,
        create_manifest: Callable[[], ResultT],
    ) -> ResultT:
        decision = self.authorize(request)
        self._require_pass(decision)
        return create_manifest()

    @staticmethod
    def _require_pass(decision) -> None:
        if decision.outcome == RightsDecisionOutcome.BLOCK:
            raise RightsGateBlocked(decision.evaluation_id, decision.reason_codes)
        if decision.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED:
            raise RightsReviewRequired(decision.evaluation_id, decision.reason_codes)


class RenderStartGuard:
    def __init__(self, gate: RightsGateService) -> None:
        self.gate = gate

    def revalidate(self, request: RightsGateRequest):
        request = request.model_copy(update={"gate_point": RightsGatePoint.RENDER_START})
        return self.gate.evaluate(request)

    def execute(
        self,
        request: RightsGateRequest,
        render: Callable[[], ResultT],
    ) -> ResultT:
        decision = self.revalidate(request)
        ManifestAdmissionGuard._require_pass(decision)
        return render()
