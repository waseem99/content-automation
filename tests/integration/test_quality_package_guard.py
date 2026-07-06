from __future__ import annotations

import pytest
from psycopg.errors import RaiseException

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


def test_publish_package_requires_quality_report(database, tmp_path):
    _, resolver, manifest, job, _, _ = publish_manifest_and_job(database, tmp_path)
    with pytest.raises(RaiseException, match="quality report"):
        with unit_of_work(database) as uow:
            uow.release_references.create(
                manifest_id=manifest.id,
                render_job_id=job["id"],
                package_hash="a" * 64,
                created_by="pytest",
            )

    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.PASS

    with unit_of_work(database) as uow:
        package = uow.release_references.create(
            manifest_id=manifest.id,
            render_job_id=job["id"],
            package_hash="b" * 64,
            created_by="pytest",
        )
    assert package["quality_report_id"] == report.id
    assert package["metadata"]["quality_status"] == "pass"


def test_human_review_report_stops_package(database, tmp_path):
    metadata = {"media": {"valid_container": True, "width": 1080, "height": 1920, "fps": 30, "duration_sec": 30, "has_audio": False}}
    _, resolver, manifest, job, _, _ = publish_manifest_and_job(database, tmp_path, output_metadata=metadata)
    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.HUMAN_REVIEW_REQUIRED
    assert "AUDIO_MISSING" in report.human_review_reasons

    with pytest.raises(RaiseException, match="passing quality report"):
        with unit_of_work(database) as uow:
            uow.release_references.create(
                manifest_id=manifest.id,
                render_job_id=job["id"],
                package_hash="c" * 64,
                created_by="pytest",
            )
