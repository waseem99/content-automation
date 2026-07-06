from __future__ import annotations

import pytest

from src.application.quality.service import QualityGateService
from src.domain.quality_models import QualityOutcome
from src.infrastructure.database.uow import unit_of_work
from tests.integration.quality_support import publish_manifest_and_job
from tests.integration.rights_support import close_database, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_media_failure_records_structured_reasons(database, tmp_path):
    metadata = {"media": {"valid_container": False, "width": 720, "height": 1280, "fps": 24, "duration_sec": 30, "has_audio": True}}
    _, resolver, _, job, _, _ = publish_manifest_and_job(database, tmp_path, output_metadata=metadata)
    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.BLOCK
    assert "OUTPUT_CORRUPTION" in report.blocking_failures
    assert "RESOLUTION_MISMATCH" in report.blocking_failures
    assert report.check_registry_version == "quality-gate-v1"
    assert report.report_hash is not None


def test_disclosure_pass_carries_text_into_package(database, tmp_path):
    _, resolver, manifest, job, _, _ = publish_manifest_and_job(database, tmp_path, attribution_required=True)
    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.PASS_WITH_DISCLOSURE
    assert report.disclosure_texts

    with unit_of_work(database) as uow:
        package = uow.release_references.create(
            manifest_id=manifest.id,
            render_job_id=job["id"],
            package_hash="d" * 64,
            created_by="pytest",
        )
    assert package["metadata"]["quality_status"] == "pass_with_disclosure"
    assert package["metadata"]["disclosure_texts"] == report.disclosure_texts


def test_changed_manifest_asset_bytes_returns_hash_failure(database, tmp_path):
    _, resolver, _, job, source, _ = publish_manifest_and_job(database, tmp_path)
    source_path = resolver.resolve(source.id).path
    source_path.write_bytes(b"changed-after-approval")
    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.BLOCK
    assert "ASSET_HASH_MISMATCH" in report.blocking_failures
