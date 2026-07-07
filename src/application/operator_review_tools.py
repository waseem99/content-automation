from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.application.p3_step_four import P3PackageReviewService
from src.application.p3_step_two import P3StepTwoService
from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.step_plan_service import StepPlanReviewService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


@dataclass(frozen=True, slots=True)
class OperatorQueueItem:
    item_type: str
    id: UUID
    workflow_run_id: UUID
    status: str
    title: str
    created_at: datetime
    metadata: dict[str, Any]


class OperatorReviewTools:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.packet_reviews = ReviewPrerequisiteService(database)
        self.output_reviews = StepPlanReviewService(database)
        self.option_reviews = P3StepTwoService(database)
        self.package_reviews = P3PackageReviewService(database)

    def queue(self, workflow_run_id: UUID) -> list[OperatorQueueItem]:
        with unit_of_work(self.database) as uow:
            rows: list[OperatorQueueItem] = []
            packet_rows = uow.conn.execute(
                """
                SELECT rp.id, rp.workflow_run_id, rr.status, ci.topic, rr.created_at,
                       rp.intake_id, rp.packet_hash
                FROM football_brief.review_prerequisites rr
                JOIN football_brief.research_packets rp ON rp.id = rr.packet_id
                JOIN football_brief.content_intakes ci ON ci.id = rp.intake_id
                WHERE rr.workflow_run_id = %s AND rr.status <> 'approved'
                ORDER BY rr.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            for row in packet_rows:
                rows.append(
                    OperatorQueueItem(
                        item_type="packet_review",
                        id=row["id"],
                        workflow_run_id=row["workflow_run_id"],
                        status=row["status"],
                        title=row["topic"] or "Untitled packet",
                        created_at=row["created_at"],
                        metadata={"intake_id": str(row["intake_id"]), "packet_hash": row["packet_hash"]},
                    )
                )

            output_rows = uow.conn.execute(
                """
                SELECT d.id, d.workflow_run_id, COALESCE(s.status, 'missing') AS status,
                       d.title, d.created_at, d.packet_id, d.intake_id, d.draft_hash
                FROM football_brief.draft_outputs d
                LEFT JOIN football_brief.source_output_reviews s
                  ON s.workflow_run_id = d.workflow_run_id AND s.source_output_id = d.id
                WHERE d.workflow_run_id = %s AND COALESCE(s.status, 'missing') <> 'approved'
                ORDER BY d.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            for row in output_rows:
                rows.append(
                    OperatorQueueItem(
                        item_type="source_output_review",
                        id=row["id"],
                        workflow_run_id=row["workflow_run_id"],
                        status=row["status"],
                        title=row["title"],
                        created_at=row["created_at"],
                        metadata={"packet_id": str(row["packet_id"]), "intake_id": str(row["intake_id"]), "draft_hash": row["draft_hash"]},
                    )
                )

            plan_rows = uow.conn.execute(
                """
                SELECT p.id, p.workflow_run_id, p.created_at, p.source_output_id,
                       p.packet_id, p.intake_id, p.plan_hash,
                       COALESCE(p.metadata->>'scene_count', '0') AS scene_count
                FROM football_brief.step_plans p
                WHERE p.workflow_run_id = %s
                ORDER BY p.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            for row in plan_rows:
                rows.append(
                    OperatorQueueItem(
                        item_type="plan_review",
                        id=row["id"],
                        workflow_run_id=row["workflow_run_id"],
                        status="review_required",
                        title="Step plan",
                        created_at=row["created_at"],
                        metadata={
                            "source_output_id": str(row["source_output_id"]),
                            "packet_id": str(row["packet_id"]),
                            "intake_id": str(row["intake_id"]),
                            "plan_hash": row["plan_hash"],
                            "scene_count": row["scene_count"],
                        },
                    )
                )

            option_rows = uow.conn.execute(
                """
                SELECT o.id, o.workflow_run_id, COALESCE(r.status, 'missing') AS status,
                       o.created_at, o.requirement_id, o.step_plan_id, o.option_hash,
                       o.reference_type, o.reference_value
                FROM football_brief.p3_options o
                LEFT JOIN football_brief.p3_option_reviews r
                  ON r.workflow_run_id = o.workflow_run_id AND r.option_id = o.id
                WHERE o.workflow_run_id = %s AND COALESCE(r.status, 'missing') <> 'approved'
                ORDER BY o.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            for row in option_rows:
                rows.append(
                    OperatorQueueItem(
                        item_type="p3_option_review",
                        id=row["id"],
                        workflow_run_id=row["workflow_run_id"],
                        status=row["status"],
                        title="P3 option",
                        created_at=row["created_at"],
                        metadata={
                            "requirement_id": str(row["requirement_id"]),
                            "step_plan_id": str(row["step_plan_id"]),
                            "option_hash": row["option_hash"],
                            "reference_type": row["reference_type"],
                            "reference_value": row["reference_value"],
                        },
                    )
                )

            package_rows = uow.conn.execute(
                """
                SELECT p.id, p.workflow_run_id, COALESCE(r.status, 'missing') AS status,
                       p.created_at, p.step_plan_id, p.package_hash, p.option_ids
                FROM football_brief.p3_packages p
                LEFT JOIN football_brief.p3_package_reviews r
                  ON r.workflow_run_id = p.workflow_run_id AND r.package_id = p.id
                WHERE p.workflow_run_id = %s AND COALESCE(r.status, 'missing') <> 'approved'
                ORDER BY p.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            for row in package_rows:
                rows.append(
                    OperatorQueueItem(
                        item_type="package_review",
                        id=row["id"],
                        workflow_run_id=row["workflow_run_id"],
                        status=row["status"],
                        title="P3 package",
                        created_at=row["created_at"],
                        metadata={
                            "step_plan_id": str(row["step_plan_id"]),
                            "package_hash": row["package_hash"],
                            "option_ids": row["option_ids"],
                        },
                    )
                )
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def approve_packet(self, *, workflow_run_id: UUID, packet_id: UUID, reviewed_by: str, rationale: str | None = None):
        return self.packet_reviews.set_packet_status(
            workflow_run_id=workflow_run_id,
            packet_id=packet_id,
            status="approved",
            reviewed_by=reviewed_by,
            rationale=rationale,
        )

    def request_output_review(self, *, workflow_run_id: UUID, source_output_id: UUID):
        return self.output_reviews.request(workflow_run_id=workflow_run_id, source_output_id=source_output_id)

    def approve_output(self, *, workflow_run_id: UUID, source_output_id: UUID, reviewed_by: str, rationale: str | None = None):
        existing = self.output_reviews.request(workflow_run_id=workflow_run_id, source_output_id=source_output_id)
        approved = self.output_reviews.approve(
            workflow_run_id=workflow_run_id,
            source_output_id=source_output_id,
            reviewed_by=reviewed_by,
            rationale=rationale,
        )
        return approved if existing else approved

    def request_option_review(self, *, workflow_run_id: UUID, option_id: UUID):
        return self.option_reviews.request_review(workflow_run_id=workflow_run_id, option_id=option_id, actor="operator")

    def approve_option(self, *, workflow_run_id: UUID, option_id: UUID, reviewed_by: str, rationale: str | None = None):
        return self.option_reviews.decide(
            workflow_run_id=workflow_run_id,
            option_id=option_id,
            status="approved",
            reviewed_by=reviewed_by,
            rationale=rationale,
        )

    def request_package_review(self, *, workflow_run_id: UUID, package_id: UUID):
        return self.package_reviews.request_review(workflow_run_id=workflow_run_id, package_id=package_id, actor="operator")

    def approve_package(self, *, workflow_run_id: UUID, package_id: UUID, reviewed_by: str, rationale: str | None = None):
        return self.package_reviews.decide(
            workflow_run_id=workflow_run_id,
            package_id=package_id,
            status="approved",
            reviewed_by=reviewed_by,
            rationale=rationale,
        )

    def package_status(self, *, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute(
                """
                SELECT p.id, p.workflow_run_id, p.step_plan_id, p.package_hash,
                       p.option_ids, p.scene_map, p.lineage_refs, p.metadata,
                       p.created_at, COALESCE(r.status, 'missing') AS review_status,
                       r.reviewed_by, r.rationale, r.reviewed_at
                FROM football_brief.p3_packages p
                LEFT JOIN football_brief.p3_package_reviews r
                  ON r.workflow_run_id = p.workflow_run_id AND r.package_id = p.id
                WHERE p.workflow_run_id = %s AND p.id = %s
                """,
                (workflow_run_id, package_id),
            ).fetchone()
            if row is None:
                raise ValueError("package was not found for workflow")
            return dict(row)

    def manifest_status(self, *, workflow_run_id: UUID, package_id: UUID | None = None) -> list[dict[str, Any]]:
        with unit_of_work(self.database) as uow:
            if package_id is None:
                rows = uow.conn.execute(
                    """
                    SELECT * FROM football_brief.p3_delivery_manifests
                    WHERE workflow_run_id = %s
                    ORDER BY created_at DESC
                    """,
                    (workflow_run_id,),
                ).fetchall()
            else:
                rows = uow.conn.execute(
                    """
                    SELECT * FROM football_brief.p3_delivery_manifests
                    WHERE workflow_run_id = %s AND package_id = %s
                    ORDER BY created_at DESC
                    """,
                    (workflow_run_id, package_id),
                ).fetchall()
            return [dict(row) for row in rows]
