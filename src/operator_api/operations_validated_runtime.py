from __future__ import annotations

from src.operations.validated_service import ValidatedOperationsService
from src.operator_api import operations_runtime as _runtime


_runtime.OperationsService = ValidatedOperationsService
install_operations_routes = _runtime.install_operations_routes


__all__ = ["install_operations_routes"]
