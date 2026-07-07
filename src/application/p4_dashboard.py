from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.p4_surface import P4OperatorSurface
from src.infrastructure.database.connection import Database


ACTION_BY_ITEM_TYPE = {
    "packet_review": "approve_packet",
    "source_output_review": "approve_output",
    "p3_option_review": "approve_option",
    "package_review": "approve_package",
    "plan_review": "open_plan_review",
}


class P4DashboardContracts:
    def __init__(self, database: Database) -> None:
        self.surface = P4OperatorSurface(database)

    def queue_cards(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        response = self.surface.queue(workflow_run_id=workflow_run_id)
        if not response.get("ok"):
            return _error("queue_cards", response.get("error", "queue unavailable"))
        cards = [_card(item) for item in response["items"]]
        return {
            "ok": True,
            "kind": "queue_cards",
            "workflow_run_id": str(workflow_run_id),
            "cards": cards,
            "count": len(cards),
        }

    def review_detail(self, *, workflow_run_id: UUID, item_type: str, resource_id: UUID) -> dict[str, Any]:
        cards = self.queue_cards(workflow_run_id=workflow_run_id)
        if not cards.get("ok"):
            return cards
        for card in cards["cards"]:
            if card["item_type"] == item_type and card["resource_id"] == str(resource_id):
                return {
                    "ok": True,
                    "kind": "review_detail",
                    "workflow_run_id": str(workflow_run_id),
                    "resource_id": str(resource_id),
                    "item_type": item_type,
                    "card": card,
                    "actions": card["actions"],
                    "metadata": card["metadata"],
                }
        return _error("review_detail", "review item was not found for workflow")

    def approval_action(self, *, action: str, workflow_run_id: UUID, resource_id: UUID, reviewed_by: str = "operator", rationale: str | None = None) -> dict[str, Any]:
        if action == "approve_packet":
            response = self.surface.approve_packet(workflow_run_id=workflow_run_id, packet_id=resource_id, reviewed_by=reviewed_by, rationale=rationale)
        elif action == "approve_output":
            response = self.surface.approve_output(workflow_run_id=workflow_run_id, source_output_id=resource_id, reviewed_by=reviewed_by, rationale=rationale)
        elif action == "approve_option":
            response = self.surface.approve_option(workflow_run_id=workflow_run_id, option_id=resource_id, reviewed_by=reviewed_by, rationale=rationale)
        elif action == "approve_package":
            response = self.surface.approve_package(workflow_run_id=workflow_run_id, package_id=resource_id, reviewed_by=reviewed_by, rationale=rationale)
        else:
            return _error("approval_action", f"unsupported action: {action}")
        if not response.get("ok"):
            return _error("approval_action", response.get("error", "approval failed"), action=action, resource_id=str(resource_id))
        return {
            "ok": True,
            "kind": "approval_action",
            "action": action,
            "workflow_run_id": str(workflow_run_id),
            "resource_id": str(resource_id),
            "status": response.get("status"),
            "reviewed_by": response.get("reviewed_by"),
            "result": response,
        }

    def package_view(self, *, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
        response = self.surface.package_status(workflow_run_id=workflow_run_id, package_id=package_id)
        if not response.get("ok"):
            return _error("package_view", response.get("error", "package unavailable"))
        return {
            "ok": True,
            "kind": "package_view",
            "workflow_run_id": str(workflow_run_id),
            "package_id": str(package_id),
            "status": response.get("review_status"),
            "package": response,
        }

    def manifest_view(self, *, workflow_run_id: UUID, package_id: UUID | None = None) -> dict[str, Any]:
        response = self.surface.manifest_status(workflow_run_id=workflow_run_id, package_id=package_id)
        if not response.get("ok"):
            return _error("manifest_view", response.get("error", "manifest unavailable"))
        return {
            "ok": True,
            "kind": "manifest_view",
            "workflow_run_id": str(workflow_run_id),
            "package_id": str(package_id) if package_id else None,
            "items": response["items"],
            "count": len(response["items"]),
        }

    def blocked_state(self, *, workflow_run_id: UUID, topic: str, source_urls: tuple[str, ...], actor: str = "operator") -> dict[str, Any]:
        response = self.surface.run_workflow(workflow_run_id=workflow_run_id, topic=topic, source_urls=source_urls, actor=actor)
        if not response.get("ok"):
            return _error("blocked_state", response.get("error", "workflow unavailable"))
        current_step = response["steps"][-1] if response.get("steps") else None
        return {
            "ok": True,
            "kind": "blocked_state",
            "workflow_run_id": str(workflow_run_id),
            "status": response.get("status"),
            "is_blocked": response.get("status") == "waiting",
            "next_action": response.get("next_action"),
            "current_step": current_step,
            "steps": response.get("steps", []),
        }

    def schema(self) -> dict[str, Any]:
        return {
            "ok": True,
            "kind": "dashboard_schema",
            "queue_card_fields": ["card_id", "resource_id", "item_type", "status", "title", "subtitle", "created_at", "actions", "metadata"],
            "review_detail_fields": ["workflow_run_id", "resource_id", "item_type", "card", "actions", "metadata"],
            "approval_action_fields": ["action", "workflow_run_id", "resource_id", "status", "reviewed_by", "result"],
            "package_view_fields": ["workflow_run_id", "package_id", "status", "package"],
            "manifest_view_fields": ["workflow_run_id", "package_id", "items", "count"],
            "blocked_state_fields": ["workflow_run_id", "status", "is_blocked", "next_action", "current_step", "steps"],
            "error_fields": ["ok", "kind", "error"],
        }


def _card(item: dict[str, Any]) -> dict[str, Any]:
    action = ACTION_BY_ITEM_TYPE.get(item["type"], "open")
    return {
        "card_id": f"{item['type']}:{item['id']}",
        "resource_id": item["id"],
        "workflow_run_id": item["workflow_run_id"],
        "item_type": item["type"],
        "status": item["status"],
        "title": item["title"],
        "subtitle": _subtitle(item),
        "created_at": item["created_at"],
        "actions": [{"name": action, "resource_id": item["id"], "enabled": action.startswith("approve_")}],
        "metadata": item.get("metadata", {}),
    }


def _subtitle(item: dict[str, Any]) -> str:
    if item["type"] == "packet_review":
        return "Research packet review required"
    if item["type"] == "source_output_review":
        return "Source output review required"
    if item["type"] == "p3_option_review":
        return "Asset option review required"
    if item["type"] == "package_review":
        return "Final package review required"
    if item["type"] == "plan_review":
        return "Step plan review required"
    return "Operator review required"


def _error(kind: str, error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "kind": kind, "error": error, **extra}
