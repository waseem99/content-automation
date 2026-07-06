from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_packets import PacketRecord
from src.infrastructure.database.repository_review_prerequisites import ReviewPrerequisiteRecord, ReviewPrerequisiteRepository
from src.infrastructure.database.uow import unit_of_work


class ReviewPrerequisiteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewRequestResult:
    review: ReviewPrerequisiteRecord
    created: bool


class ReviewPrerequisiteService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request_for_packet(self, *, workflow_run_id: UUID, packet_id: UUID, requested_by: str) -> ReviewRequestResult:
        with unit_of_work(self.database) as uow:
            packet = self._packet(uow.conn, workflow_run_id, packet_id)
            repo = ReviewPrerequisiteRepository(uow.conn)
            existing = repo.get_for_packet(workflow_run_id=workflow_run_id, packet_id=packet_id)
            review = repo.create_pending(
                workflow_run_id=workflow_run_id,
                packet_id=packet_id,
                intake_id=packet.intake_id,
                requested_by=requested_by,
            )
            if existing is None:
                uow.workflow_events.create(
                    workflow_run_id=workflow_run_id,
                    stage_execution_id=packet.stage_execution_id,
                    event_type="review_prerequisite_requested",
                    actor=requested_by,
                    reason="packet_review_required",
                    payload={"packet_id": str(packet_id), "review_id": str(review.id)},
                )
            return ReviewRequestResult(review=review, created=existing is None)

    def set_packet_status(self, *, workflow_run_id: UUID, packet_id: UUID, status: str, reviewed_by: str, rationale: str | None = None) -> ReviewPrerequisiteRecord:
        if status not in {"approved", "changes_requested", "rejected"}:
            raise ReviewPrerequisiteError("unsupported review status")
        with unit_of_work(self.database) as uow:
            packet = self._packet(uow.conn, workflow_run_id, packet_id)
            repo = ReviewPrerequisiteRepository(uow.conn)
            existing = repo.get_for_packet(workflow_run_id=workflow_run_id, packet_id=packet_id)
            if existing is None:
                raise ReviewPrerequisiteError("review prerequisite is missing")
            review = repo.set_status(
                workflow_run_id=workflow_run_id,
                packet_id=packet_id,
                status=status,
                reviewed_by=reviewed_by,
                rationale=rationale,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=packet.stage_execution_id,
                event_type="review_prerequisite_decided",
                actor=reviewed_by,
                reason=status,
                payload={"packet_id": str(packet_id), "review_id": str(review.id), "status": status},
            )
            return review

    def require_packet_approved(self, *, workflow_run_id: UUID, packet_id: UUID) -> PacketRecord:
        with unit_of_work(self.database) as uow:
            packet = self._packet(uow.conn, workflow_run_id, packet_id)
            review = ReviewPrerequisiteRepository(uow.conn).get_for_packet(workflow_run_id=workflow_run_id, packet_id=packet_id)
            if review is None:
                raise ReviewPrerequisiteError("review prerequisite is missing")
            if review.status != "approved":
                raise ReviewPrerequisiteError("packet is not approved for draft work")
            return packet

    def pending_for_workflow(self, workflow_run_id: UUID) -> list[ReviewPrerequisiteRecord]:
        with unit_of_work(self.database) as uow:
            return ReviewPrerequisiteRepository(uow.conn).list_pending(workflow_run_id)

    @staticmethod
    def _packet(conn, workflow_run_id: UUID, packet_id: UUID) -> PacketRecord:
        row = conn.execute(
            "SELECT * FROM football_brief.research_packets WHERE id = %s AND workflow_run_id = %s",
            (packet_id, workflow_run_id),
        ).fetchone()
        if row is None:
            raise ReviewPrerequisiteError("packet was not found for workflow")
        return PacketRecord(**row)
