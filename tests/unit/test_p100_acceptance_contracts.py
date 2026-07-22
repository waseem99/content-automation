from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import (
    EvidenceCategory,
    OperationsEvidenceRequest,
    PilotCreateRequest,
    PilotItemRequest,
)
from src.application.acceptance.validated_service import ValidatedAcceptancePilotService


ROOT = Path(__file__).resolve().parents[2]


def test_pilot_scope_is_fixed_to_two_items_per_required_brand() -> None:
    request = PilotCreateRequest(pilot_key="p100-controlled-pilot")
    assert request.canonical_scope() == {
        "brand_slugs": ["animal-x", "rawr-nation"],
        "items_per_brand": 2,
        "total_items": 4,
        "required_modes": ["local_only", "managed_render"],
        "staging_delivery": "simulated_only",
        "live_delivery": "external_evidence_after_signoff",
    }


def test_revision_contract_rejects_unknown_or_empty_stages() -> None:
    common = {
        "portfolio_content_id": "00000000-0000-0000-0000-000000000001",
        "content_version": 1,
        "production_mode": "local_only",
    }
    with pytest.raises(ValidationError):
        PilotItemRequest(**common, required_revision_stages=())
    with pytest.raises(ValidationError):
        PilotItemRequest(**common, required_revision_stages=("script", "unknown"))


def test_manual_subject_binding_is_limited_to_operations_evidence() -> None:
    with pytest.raises(ValidationError, match="limited to operations evidence"):
        OperationsEvidenceRequest(
            category=EvidenceCategory.SCRIPT_APPROVAL,
            subject_type="script_version",
            subject_id="00000000-0000-0000-0000-000000000001",
        )
    accepted = OperationsEvidenceRequest(
        category=EvidenceCategory.WORKER_RESTART,
        subject_type="operations_drill_run",
        subject_id="00000000-0000-0000-0000-000000000001",
    )
    assert accepted.category is EvidenceCategory.WORKER_RESTART


def test_public_service_uses_stable_aggregate_evidence_subjects() -> None:
    assert AcceptancePilotService is ValidatedAcceptancePilotService
    result = AcceptancePilotService._result(
        True,
        "operator_brand_assignments",
        {"brand_id": "00000000-0000-0000-0000-000000000001", "role_counts": {"admin": 1}},
    )
    assert result["passed"] is True
    assert result["subject_id"].startswith("aggregate:")
    assert len(result["subject_id"].split(":", 1)[1]) == 64


def test_exact_subject_types_use_their_canonical_child_ids() -> None:
    mix = AcceptancePilotService._result(
        True,
        "audio_mix_version",
        {"id": "00000000-0000-0000-0000-000000000001", "mix_id": "00000000-0000-0000-0000-000000000002"},
    )
    spend = AcceptancePilotService._result(
        True,
        "production_spend_decision",
        {"id": "00000000-0000-0000-0000-000000000003", "spend_decision_id": "00000000-0000-0000-0000-000000000004"},
    )
    artifact = AcceptancePilotService._result(
        True,
        "shared_artifact_version",
        {"id": "00000000-0000-0000-0000-000000000005", "output_artifact_version_id": "00000000-0000-0000-0000-000000000006"},
    )
    assert mix["subject_id"].endswith("0002")
    assert spend["subject_id"].endswith("0004")
    assert artifact["subject_id"].endswith("0006")


def test_p100_contains_no_live_delivery_execution_surface() -> None:
    runtime = (ROOT / "src/operator_api/acceptance_runtime.py").read_text(encoding="utf-8")
    service = (ROOT / "src/application/acceptance/service.py").read_text(encoding="utf-8")
    foundation = (ROOT / "migrations/0083_acceptance_pilot_foundation.sql").read_text(encoding="utf-8")
    combined = "\n".join((runtime, service, foundation)).lower()
    assert "live-delivery-evidence" in combined
    for forbidden in (
        "execute_live_delivery",
        "submit_live_delivery",
        "live_adapter",
        "credential_secret_ref",
        "vercel deploy",
        "docker push",
    ):
        assert forbidden not in combined
    assert "does not enable live delivery adapters" in foundation.lower()


def test_database_gates_require_per_brand_modes_evidence_and_three_signoffs() -> None:
    integrity = (ROOT / "migrations/0084_acceptance_pilot_integrity.sql").read_text(encoding="utf-8")
    hardening = (ROOT / "migrations/0085_acceptance_pilot_evidence_hardening.sql").read_text(encoding="utf-8")
    subject_integrity = (ROOT / "migrations/0086_acceptance_signoff_and_subject_integrity.sql").read_text(encoding="utf-8")
    assert "exactly one local-only and one managed-render item" in hardening
    assert "Admin, Reviewer, and Publisher approval are required" in integrity
    assert "Pilot item pass requires all content evidence" in hardening
    assert "At least one separately signed-off live-delivery result is required" in integrity
    assert "sign-offs require distinct operators" in subject_integrity
    assert "exact pilot item lineage" in subject_integrity
