from src.infrastructure.database.executemany_patch import (
    install_executemany_connection_patch,
)

install_executemany_connection_patch()

from src.application.mass_operations.service import MassOperationError
from src.application.mass_operations.final_service import ValidatedMassOperationService

MassOperationService = ValidatedMassOperationService

__all__ = ["MassOperationError", "MassOperationService", "ValidatedMassOperationService"]
