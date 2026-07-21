from pathlib import Path

import pytest

from src.application.generation_jobs.legacy_adapter import normalize_legacy_record
from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import canonical_fingerprint
from src.operator_api.access import AccessPermission, OperatorIdentity, OperatorRole
from src.operator_api.generation_jobs_runtime import (
    allowed_worker_job_types,
    permission_for_job_type,
)


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_fingerprint_is_order_independent_and_content_sensitive() -> None:
    first = canonical_fingerprint({"b": [2, 3], "a": 1})
    second = canonical_fingerprint({"a": 1, "b": [2, 3]})
    changed = canonical_fingerprint({"a": 1, "b": [3, 2]})
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_enqueue_contract_requires_workflow_pair_and_unique_dependencies() -> None:
    with pytest.raises(ValueError, match="production_workflow_id"):
        GenerationJobEnqueue(
            portfolio_content_id="11111111-1111-1111-1111-111111111111",
            content_version=1,
            production_workflow_version_id="22222222-2222-2222-2222-222222222222",
            job_type=GenerationJobType.SCRIPT,
            idempotency_key="script:content:version:1",
            input_payload={"topic": "test"},
        )
    with pytest.raises(ValueError, match="must be unique"):
        GenerationJobEnqueue(
            portfolio_content_id="11111111-1111-1111-1111-111111111111",
            content_version=1,
            job_type=GenerationJobType.SCRIPT,
            idempotency_key="script:content:version:2",
            input_payload={"topic": "test"},
            dependency_job_ids=(
                "33333333-3333-3333-3333-333333333333",
                "33333333-3333-3333-3333-333333333333",
            ),
        )


def identity(*roles: OperatorRole) -> OperatorIdentity:
    return OperatorIdentity(
        operator_id="person.one",
        key_name="test",
        display_name="Person One",
        roles=frozenset(roles),
        brand_ids=frozenset({"11111111-1111-1111-1111-111111111111"}),
        active=True,
    )


def test_worker_roles_separate_generation_and_publishing() -> None:
    producer_types = allowed_worker_job_types(identity(OperatorRole.PRODUCER))
    publisher_types = allowed_worker_job_types(identity(OperatorRole.PUBLISHER))
    admin_types = allowed_worker_job_types(identity(OperatorRole.ADMIN))

    assert GenerationJobType.KEYFRAME in producer_types
    assert GenerationJobType.PUBLISHING not in producer_types
    assert publisher_types == {GenerationJobType.PUBLISHING}
    assert admin_types == set(GenerationJobType)
    assert permission_for_job_type(GenerationJobType.PUBLISHING) == AccessPermission.DELIVER_RELEASE
    assert permission_for_job_type(GenerationJobType.PREVIEW) == AccessPermission.RUN_PRODUCTION


def test_legacy_normalizer_accepts_p68_style_fields_without_copying_media() -> None:
    record = normalize_legacy_record(
        {
            "job_id": "p68-001",
            "state": "running",
            "type": "keyframe",
            "input": {"prompt": "ocean wildlife"},
            "output_path": "D:/p68/frames/001.png",
            "worker": "p68.local",
            "attempts": [{"status": "failed"}, {"status": "running"}],
        },
        index=1,
    )
    assert record.legacy_id == "p68-001"
    assert record.status == "running"
    assert record.job_type == GenerationJobType.KEYFRAME
    assert record.attempt_count == 2
    assert record.output_payload is None
    assert record.metadata["legacy_path"] == "D:/p68/frames/001.png"


def test_migrations_runtime_and_adapter_are_wired() -> None:
    migration = (ROOT / "migrations" / "0032_unified_generation_jobs.sql").read_text(encoding="utf-8")
    hardening = (ROOT / "migrations" / "0033_generation_job_queue_hardening.sql").read_text(encoding="utf-8")
    runtime_factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "generation_jobs" / "service.py").read_text(encoding="utf-8")
    adapter = (ROOT / "src" / "application" / "generation_jobs" / "legacy_adapter.py").read_text(encoding="utf-8")

    assert "CREATE TABLE football_brief.generation_jobs" in migration
    assert "CREATE TABLE football_brief.generation_job_attempts" in migration
    assert "CREATE TABLE football_brief.generation_job_dependencies" in migration
    assert "CREATE TABLE football_brief.generation_job_events" in migration
    assert "FOR UPDATE OF j SKIP LOCKED" in service
    assert "generation_job_lease_token_invalid" in service
    assert "content_version_superseded" in service
    assert "import_legacy_terminal" in service
    assert "load_legacy_records" in adapter
    assert "install_generation_job_routes" in runtime_factory
    assert "OLD.status = 'queued' AND NEW.status IN ('running', 'cancelled', 'dead_letter')" in hardening
    assert hardening.rstrip().endswith("COMMIT;")
