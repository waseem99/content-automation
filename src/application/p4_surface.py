from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable
from uuid import UUID

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools, OperatorQueueItem
from src.application.p4_control import P4ControlRequest, P4ControlService
from src.infrastructure.database.connection import Database


class P4SurfaceError(RuntimeError):
    pass


class P4OperatorSurface:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.operators = OperatorReviewTools(database)

    def create_intake(self, *, workflow_run_id: UUID, topic: str | None = None, source_urls: tuple[str, ...] = (), actor: str = "operator") -> dict[str, Any]:
        return self._wrap(
            "intake_create",
            lambda: _intake_payload(
                SourceIntakeService(self.database).create(
                    CreateIntakeRequest(
                        workflow_run_id=workflow_run_id,
                        topic=topic,
                        source_urls=source_urls,
                        created_by=actor,
                    )
                )
            ),
        )

    def run_workflow(self, *, workflow_run_id: UUID, topic: str, source_urls: tuple[str, ...], actor: str = "operator") -> dict[str, Any]:
        return self._wrap(
            "workflow_run",
            lambda: P4ControlService(self.database)
            .run_until_waiting(
                P4ControlRequest(
                    workflow_run_id=workflow_run_id,
                    topic=topic,
                    source_urls=source_urls,
                    actor=actor,
                )
            )
            .as_dict(),
        )

    def queue(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        return self._wrap(
            "queue",
            lambda: {
                "workflow_run_id": str(workflow_run_id),
                "items": [_queue_item_payload(item) for item in self.operators.queue(workflow_run_id)],
            },
        )

    def approve_packet(self, *, workflow_run_id: UUID, packet_id: UUID, reviewed_by: str = "operator", rationale: str | None = None) -> dict[str, Any]:
        return self._wrap(
            "approve_packet",
            lambda: _record_payload(
                self.operators.approve_packet(
                    workflow_run_id=workflow_run_id,
                    packet_id=packet_id,
                    reviewed_by=reviewed_by,
                    rationale=rationale,
                )
            ),
        )

    def approve_output(self, *, workflow_run_id: UUID, source_output_id: UUID, reviewed_by: str = "operator", rationale: str | None = None) -> dict[str, Any]:
        return self._wrap(
            "approve_output",
            lambda: _record_payload(
                self.operators.approve_output(
                    workflow_run_id=workflow_run_id,
                    source_output_id=source_output_id,
                    reviewed_by=reviewed_by,
                    rationale=rationale,
                )
            ),
        )

    def request_option(self, *, workflow_run_id: UUID, option_id: UUID) -> dict[str, Any]:
        return self._wrap(
            "request_option",
            lambda: _record_payload(self.operators.request_option_review(workflow_run_id=workflow_run_id, option_id=option_id)),
        )

    def approve_option(self, *, workflow_run_id: UUID, option_id: UUID, reviewed_by: str = "operator", rationale: str | None = None) -> dict[str, Any]:
        return self._wrap(
            "approve_option",
            lambda: _record_payload(
                self.operators.approve_option(
                    workflow_run_id=workflow_run_id,
                    option_id=option_id,
                    reviewed_by=reviewed_by,
                    rationale=rationale,
                )
            ),
        )

    def request_package(self, *, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
        return self._wrap(
            "request_package",
            lambda: _record_payload(self.operators.request_package_review(workflow_run_id=workflow_run_id, package_id=package_id)),
        )

    def approve_package(self, *, workflow_run_id: UUID, package_id: UUID, reviewed_by: str = "operator", rationale: str | None = None) -> dict[str, Any]:
        return self._wrap(
            "approve_package",
            lambda: _record_payload(
                self.operators.approve_package(
                    workflow_run_id=workflow_run_id,
                    package_id=package_id,
                    reviewed_by=reviewed_by,
                    rationale=rationale,
                )
            ),
        )

    def package_status(self, *, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
        return self._wrap(
            "package_status",
            lambda: self.operators.package_status(workflow_run_id=workflow_run_id, package_id=package_id),
        )

    def manifest_status(self, *, workflow_run_id: UUID, package_id: UUID | None = None) -> dict[str, Any]:
        return self._wrap(
            "manifest_status",
            lambda: {
                "workflow_run_id": str(workflow_run_id),
                "package_id": str(package_id) if package_id else None,
                "items": self.operators.manifest_status(workflow_run_id=workflow_run_id, package_id=package_id),
            },
        )

    def _wrap(self, kind: str, callback: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            payload = callback()
            return _json_ready({"ok": True, "kind": kind, **payload})
        except Exception as exc:
            return {"ok": False, "kind": kind, "error": str(exc)}


def _intake_payload(result) -> dict[str, Any]:
    return {
        "id": str(result.intake.id),
        "workflow_run_id": str(result.intake.workflow_run_id),
        "created": result.created,
        "topic": result.intake.topic,
        "status": result.intake.status,
        "canonical_input_hash": result.intake.canonical_input_hash,
        "reference_count": len(result.references),
        "created_at": result.intake.created_at,
    }


def _queue_item_payload(item: OperatorQueueItem) -> dict[str, Any]:
    return {
        "type": item.item_type,
        "id": str(item.id),
        "workflow_run_id": str(item.workflow_run_id),
        "status": item.status,
        "title": item.title,
        "created_at": item.created_at,
        "metadata": item.metadata,
    }


def _record_payload(record) -> dict[str, Any]:
    if hasattr(record, "__dataclass_fields__"):
        return {name: getattr(record, name) for name in record.__dataclass_fields__}
    return dict(record)


def _json_ready(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value
