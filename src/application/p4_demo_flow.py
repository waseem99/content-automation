from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.application.p4_dashboard import P4DashboardContracts
from src.infrastructure.database.connection import Database


@dataclass(frozen=True, slots=True)
class P4DemoFlow:
    scenario_id: str = "p4-demo-flow"
    title: str = "P4 Demo Flow"
    topic: str = "Football match preview demo"
    source_urls: tuple[str, ...] = ("https://example.com/p4-demo/source-a", "https://example.com/p4-demo/source-b")
    actor: str = "demo-operator"
    stop_points: tuple[str, ...] = ("approve_packet", "approve_output", "continue_p3_delivery")

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "topic": self.topic,
            "source_urls": list(self.source_urls),
            "actor": self.actor,
            "expected_stop_points": list(self.stop_points),
        }


P4_DEMO_FLOW = P4DemoFlow()


class P4DemoFlowService:
    def __init__(self, database: Database) -> None:
        self.dashboard = P4DashboardContracts(database)

    def scenario(self) -> dict[str, Any]:
        return {"ok": True, "kind": "demo_scenario", **P4_DEMO_FLOW.as_dict()}

    def start(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        return self.dashboard.blocked_state(
            workflow_run_id=workflow_run_id,
            topic=P4_DEMO_FLOW.topic,
            source_urls=P4_DEMO_FLOW.source_urls,
            actor=P4_DEMO_FLOW.actor,
        )

    def approve_current(self, *, workflow_run_id: UUID, reviewed_by: str = "demo-reviewer", rationale: str | None = None) -> dict[str, Any]:
        state = self.start(workflow_run_id=workflow_run_id)
        if not state.get("ok"):
            return state
        next_action = state.get("next_action")
        if next_action not in {"approve_packet", "approve_output"}:
            return {"ok": False, "kind": "demo_approval", "error": "no supported demo action", "next_action": next_action}
        cards = self.dashboard.queue_cards(workflow_run_id=workflow_run_id)
        if not cards.get("ok"):
            return {"ok": False, "kind": "demo_approval", "error": cards.get("error", "queue unavailable"), "next_action": next_action}
        for card in cards.get("cards", []):
            if any(action.get("name") == next_action for action in card.get("actions", [])):
                return self.dashboard.approval_action(
                    action=next_action,
                    workflow_run_id=workflow_run_id,
                    resource_id=UUID(card["resource_id"]),
                    reviewed_by=reviewed_by,
                    rationale=rationale or "Demo approval",
                )
        return {"ok": False, "kind": "demo_approval", "error": "matching queue card was not found", "next_action": next_action}

    def status(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        state = self.start(workflow_run_id=workflow_run_id)
        queue = self.dashboard.queue_cards(workflow_run_id=workflow_run_id)
        return {"ok": bool(state.get("ok") and queue.get("ok")), "kind": "demo_status", "scenario": P4_DEMO_FLOW.as_dict(), "state": state, "queue": queue}
