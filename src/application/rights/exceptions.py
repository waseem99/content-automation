from __future__ import annotations

from uuid import UUID

from src.application.rights.reason_codes import RightsReasonCode


class RightsError(RuntimeError):
    pass


class RightsApprovalError(RightsError):
    def __init__(self, reason: RightsReasonCode, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class RightsGateBlocked(RightsError):
    def __init__(self, evaluation_id: UUID, reasons: tuple[RightsReasonCode, ...]) -> None:
        super().__init__(f"Rights gate blocked evaluation {evaluation_id}")
        self.evaluation_id = evaluation_id
        self.reasons = reasons


class RightsReviewRequired(RightsError):
    def __init__(self, evaluation_id: UUID, reasons: tuple[RightsReasonCode, ...]) -> None:
        super().__init__(f"Rights review required for evaluation {evaluation_id}")
        self.evaluation_id = evaluation_id
        self.reasons = reasons


class RightsPolicyUnavailable(RightsError):
    pass


class RightsDecisionPersistenceError(RightsError):
    pass
