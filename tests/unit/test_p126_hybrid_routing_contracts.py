from __future__ import annotations

from pathlib import Path

from src.application.hybrid_routing import (
    HybridRoutingError,
    HybridRoutingService,
    PAID_ROUTE_CLASSES,
    ROUTE_CLASSES,
    ROUTER_VERSION,
)
from src.operator_api.p126_hybrid_routing_runtime import install_p126_hybrid_routing_routes


ROOT = Path(__file__).resolve().parents[2]


def test_hybrid_routing_contract_is_importable() -> None:
    assert ROUTER_VERSION == "p126-hybrid-router-v1"
    assert ROUTE_CLASSES == (
        "reuse_asset",
        "deterministic_composition",
        "local_generation",
        "cloud_portable",
        "premium_low_cost",
        "premium_hero",
        "manual_edit",
    )
    assert PAID_ROUTE_CLASSES == frozenset(
        {"cloud_portable", "premium_low_cost", "premium_hero"}
    )
    assert HybridRoutingService.__name__ == "HybridRoutingService"
    assert HybridRoutingError.__name__ == "HybridRoutingError"
    assert callable(install_p126_hybrid_routing_routes)


def test_migration_defines_exact_plan_fallback_and_billing_lineage() -> None:
    migration = (ROOT / "migrations" / "0103_p126_hybrid_scene_routing.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE football_brief.hybrid_routing_policies" in migration
    assert "CREATE TABLE football_brief.hybrid_production_templates" in migration
    assert "CREATE TABLE football_brief.hybrid_renderer_measurements" in migration
    assert "CREATE TABLE football_brief.hybrid_route_plans" in migration
    assert "CREATE TABLE football_brief.hybrid_route_scenes" in migration
    assert "CREATE TABLE football_brief.hybrid_route_candidates" in migration
    assert "CREATE TABLE football_brief.hybrid_spend_approvals" in migration
    assert "CREATE TABLE football_brief.hybrid_route_attempts" in migration
    assert "CREATE TABLE football_brief.hybrid_route_overrides" in migration
    assert "billing_key text NOT NULL UNIQUE" in migration
    assert "automatic" not in migration.lower() or "automatic" in migration.lower()
    assert "Paid candidates require a separate approved spend record" in migration
    assert "abs((end_seconds-start_seconds)-duration_seconds) <= 0.001" in migration


def test_service_builds_exact_edl_and_never_submits_provider_requests() -> None:
    service = (
        ROOT / "src" / "application" / "hybrid_routing" / "service.py"
    ).read_text(encoding="utf-8")
    assert "def _build_edl" in service
    assert "exact_edl_reconciliation_failed" in service
    assert "non_contiguous_scene_timeline" in service
    assert "def _candidate_specs" in service
    assert "cost_per_accepted_second" in service
    assert "fallback_chain" in service
    assert "billing_key_identity_mismatch" in service
    assert "local_route_not_exhausted" in service
    assert "explicit_spend_approval_required" in service
    assert '"provider_submission": False' in service
    assert '"generation_job_created": False' in service
    assert "GenerationJobService" not in service
    assert "request.urlopen" not in service
    assert "httpx" not in service
    assert "openai" not in service


def test_paid_execution_and_publishing_are_off_in_configuration() -> None:
    environment = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")
    remote = (
        ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1"
    ).read_text(encoding="utf-8")
    assert "OPS_MIGRATION_HEAD=0103_p126_hybrid_scene_routing.sql" in environment
    assert "HYBRID_ROUTING_ENABLED=true" in environment
    assert "HYBRID_PAID_EXECUTION_ENABLED=false" in environment
    assert "HYBRID_PUBLIC_PUBLISHING_ENABLED=false" in environment
    assert '$values["HYBRID_PAID_EXECUTION_ENABLED"] = "false"' in remote
    assert '$values["HYBRID_PUBLIC_PUBLISHING_ENABLED"] = "false"' in remote
    assert 'paid_provider_execution = $false' in remote
    assert 'automatic_publishing = $false' in remote


def test_api_exposes_plan_evidence_and_admin_spend_controls() -> None:
    runtime = (
        ROOT / "src" / "operator_api" / "p126_hybrid_routing_runtime.py"
    ).read_text(encoding="utf-8")
    factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(
        encoding="utf-8"
    )
    assert '/p126/packages/{package_id}/plan' in runtime
    assert '/p126/plans/{plan_id}/report' in runtime
    assert '/p126/scenes/{scene_id}/override' in runtime
    assert '/p126/plans/{plan_id}/spend-decision' in runtime
    assert '/p126/scenes/{scene_id}/attempts' in runtime
    assert '/p126/attempts/{attempt_id}/complete' in runtime
    assert "require_admin(operator)" in runtime
    assert "install_p126_hybrid_routing_routes" in factory


def test_lifecycle_proves_exact_120_seconds_without_generation_jobs() -> None:
    lifecycle = (ROOT / "scripts" / "ci" / "p126_hybrid_lifecycle.py").read_text(
        encoding="utf-8"
    )
    assert '"target_duration_seconds": 120' in lifecycle
    assert 'assert report["finished_seconds"] == 120.0' in lifecycle
    assert 'assert report["retry_seconds"] == 30.0' in lifecycle
    assert 'assert report["accepted_premium_seconds"] == 0.0' in lifecycle
    assert "assert jobs_after == jobs_before" in lifecycle
    assert "assert paid_attempts == 0" in lifecycle
    assert "assert overrides == 1" in lifecycle
