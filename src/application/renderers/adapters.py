from __future__ import annotations

from typing import Protocol

from src.application.renderers.models import RendererAdapterResult, RendererSubmissionRequest


class RendererAdapterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ProductionRendererAdapter(Protocol):
    adapter_key: str

    def submit(self, request: RendererSubmissionRequest, *, catalogue_entry: dict) -> RendererAdapterResult:
        ...


class SimulatedProductionRendererAdapter:
    adapter_key = "simulated"

    def submit(self, request: RendererSubmissionRequest, *, catalogue_entry: dict) -> RendererAdapterResult:
        behavior = str(catalogue_entry.get("configuration", {}).get("simulation_behavior", "success"))
        if behavior == "fail":
            raise RendererAdapterError("simulated_renderer_failure", "The simulated renderer was configured to fail.")
        return RendererAdapterResult(
            provider_request_id=f"simulated:{request.idempotency_key}",
            output_payload={
                "kind": "simulated_production_render",
                "renderer_key": catalogue_entry["renderer_key"],
                "renderer_version": catalogue_entry["version"],
                "format": request.request.output_format,
                "duration_seconds": str(request.request.duration_seconds),
                "width": request.request.width,
                "height": request.request.height,
                "simulated": True,
            },
            actual_cost_usd=0,
        )


def default_adapter_registry() -> dict[str, ProductionRendererAdapter]:
    return {"simulated": SimulatedProductionRendererAdapter()}
