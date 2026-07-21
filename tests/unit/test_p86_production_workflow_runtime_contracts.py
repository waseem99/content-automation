from pathlib import Path

from src.domain.production_workflow import ProductionStage
from src.operator_api.access import AccessPermission
from src.operator_api.production_workflow_runtime import delivery_or_production_permission


ROOT = Path(__file__).resolve().parents[2]


def test_delivery_stages_remain_separate_from_production_permissions() -> None:
    assert delivery_or_production_permission(ProductionStage.SCRIPT_DRAFT) == AccessPermission.RUN_PRODUCTION
    assert delivery_or_production_permission(ProductionStage.SCHEDULING) == AccessPermission.DELIVER_RELEASE
    assert delivery_or_production_permission(ProductionStage.PUBLICATION) == AccessPermission.DELIVER_RELEASE


def test_runtime_is_registered_and_enforces_assignment_and_comment_ownership() -> None:
    runtime_factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "operator_api" / "production_workflow_runtime.py").read_text(encoding="utf-8")

    assert "install_production_workflow_routes" in runtime_factory
    assert "require_current_assignment" in runtime
    assert "workflow_assigned_to_another_operator" in runtime
    assert "require_comment_in_workflow" in runtime
    assert "/production/workflows/{workflow_id}/comments/{comment_id}/resolve" in runtime


def test_migration_prevents_status_reopening_partial_resolution_and_evidence_deletion() -> None:
    migration = (ROOT / "migrations" / "0031_versioned_production_workflow.sql").read_text(encoding="utf-8")

    assert "Invalid production workflow version status transition" in migration
    assert "resolved_comment_is_consistent" in migration
    assert "Production workflow versions are immutable evidence" in migration
    assert "Workflow assignments cannot be deleted" in migration
    assert "Workflow comments cannot be deleted" in migration
    assert "BEFORE UPDATE OR DELETE ON football_brief.production_workflow_versions" in migration
    assert "BEFORE UPDATE OR DELETE ON football_brief.production_workflow_assignments" in migration
    assert "BEFORE UPDATE OR DELETE ON football_brief.production_workflow_comments" in migration
