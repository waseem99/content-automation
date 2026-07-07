from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.application.p4_dashboard import P4DashboardContracts
from src.infrastructure.database.connection import Database


@dataclass(frozen=True, slots=True)
class P4DemoScenario:
    scenario_id: str
    title: str
    topic: str
    source_urls: tuple[str, ...]
    actor: str
    expected_stop_points: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "topic": self.topic,
            "source_urls": list(self.source_urls),
            "actor": self.actor,
            "expected_stop_points": list(self.expected_stop_points),
            "notes": list(self.notes),
        }


P4_DEMO_SCENARIO = P4DemoScenario(
    scenario_id="p4-demo-derby-preview",
    title="P4 Demo Derby Preview",
    topic="Derby preview: tactical momentum, selection risks, and match narrative",
    source_urls=("https://example.com/p4-demo/derby-preview-source-a", "https://example.com/p4-demo/derby-preview-source-b"),
    actor="demo-operator",
    expected_stop_points=("approve_packet", "approve_output", "continue_p3_delivery"),
    notes=(
        "Uses static example URLs only; no network calls are made by the scenario.",
        "The control path must stop at packet review before draft/source-output creation.",
        "After packet approval, it must stop at source-output review.",
        "After source-output approval, it must create a step plan and stop before P3 delivery controls.",
    ),
)


class P4DemoService:
    def __init__(self, database: Database) -> None:
        self.dashboard = P4DashboardContracts(database)

    def scenario(self) -> dict[str, Any]:
        return {"ok": True, "kind": "demo_scenario", **P4_DEMO_SCENARIO.as_dict()}

    def start(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        return self.dashboard.blocked_state(
            workflow_run_id=workflow_run_id,
            topic=P4_DEMO_SCENARIO.topic,
            source_urls=P4_DEMO_SCENARIO.source_urls,
            actor=P4_DEMO_SCENARIO.actor,
        )

    def approve_current(self, *, workflow_run_id: UUID, reviewed_by: str = "demo-reviewer", rationale: str | None = None) -> dict[str, Any]:
        state = self.start(workflow_run_id=workflow_run_id)
        if not state.get("ok"):
            return state
        next_action = state.get("next_action")
        if next_action not in {"approve_packet", "approve_output"}:
            return {
                "ok": False,
                "kind": "demo_approval",
                "error": f"no supported demo approval is available for next_action={next_action}",
                "next_action": next_action,
            }
        current_step = state.get("current_step") or {}
        resource_id = current_step.get("resource_id")
        if not resource_id:
            return {"ok": False, "kind": "demo_approval", "error": "blocked state has no resource id", "next_action": next_action}
        return self.dashboard.approval_action(
            action=next_action,
            workflow_run_id=workflow_run_id,
            resource_id=UUID(resource_id),
            reviewed_by=reviewed_by,
            rationale=rationale or f"Demo approval for {next_action}",
        )

    def status(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        state = self.start(workflow_run_id=workflow_run_id)
        cards = self.dashboard.queue_cards(workflow_run_id=workflow_run_id)
        return {
            "ok": state.get("ok", False) and cards.get("ok", False),
            "kind": "demo_status",
            "scenario": P4_DEMO_SCENARIO.as_dict(),
            "state": state,
            "queue": cards,
        }
