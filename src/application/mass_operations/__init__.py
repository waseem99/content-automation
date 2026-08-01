from src.application.mass_operations.service import MassOperationError
from src.application.mass_operations.final_service import ValidatedMassOperationService

MassOperationService = ValidatedMassOperationService

__all__ = ["MassOperationError", "MassOperationService", "ValidatedMassOperationService"]
