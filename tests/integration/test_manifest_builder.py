from __future__ import annotations

from pathlib import Path

import pytest
from psycopg.errors import RaiseException

from src.application.assets.classification import AssetContext
from src.application.manifests.builder import RenderManifestBuilder
from src.application.manifests.exceptions import ManifestValidationError
from src.domain.render_status import RenderManifestStatus, RenderMode
from tests.integration.manifest_support import (
    SCRIPT_HASH,
    build_request,
    create_approval_review,
    create_manifest_workflow,
    create_passing_gate,
    register_manifest_versions,
)
from tests.integration.rights_support import (
    approve_rights,
    close_database,
    database_fixture,
    register_asset,
    registry_for,
)


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _publish_context(database, tmp_path: Path, *, script_hash: str = SCRIPT_HASH):
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "image.png"
    evidence = tmp_path / "evidence" / "license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"manifest-image")
    evidence.write_bytes(b"manifest-license")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        territories=["US"],
    )
    gate_id = create_passing_gate(database, tmp_path, workflow_id, asset.id)
    review_id = create_approval_review(
        database,
        workflow_id,
        [asset.id],
        script_hash=script_hash,
    )
    return content_id, workflow_id, asset, gate_id, review_id


def test_preview_manifest_seals_with_placeholder_and_watermark(database) -> None:
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    record = RenderManifestBuilder(database).build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PREVIEW,
        )
    )
    assert record.status == RenderManifestStatus.SEALED
    assert record.document.not_for_publication is True
    assert record.document.watermark_text == "PREVIEW - NOT FOR PUBLICATION"
    assert record.document.assets[0].is_placeholder


def test_publish_manifest_uses_gate_rights_and_human_approval(database, tmp_path: Path) -> None:
    content_id, workflow_id, asset, gate_id, review_id = _publish_context(
        database, tmp_path
    )
    record = RenderManifestBuilder(database).build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PUBLISH,
            asset_id=asset.id,
            rights_gate_evaluation_id=gate_id,
            approval_review_id=review_id,
        )
    )
    assert record.status == RenderManifestStatus.APPROVED
    assert record.document.approval is not None
    assert record.document.rights_evaluation is not None
    assert record.document.assets[0].asset_rights_id is not None
    assert record.document.assets[0].rights_evidence_ids


def test_identical_material_reuses_manifest(database) -> None:
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    request = build_request(
        content_id=content_id,
        workflow_id=workflow_id,
        mode=RenderMode.PREVIEW,
    )
    first = RenderManifestBuilder(database).build(request)
    second = RenderManifestBuilder(database).build(request)
    assert first.id == second.id
    assert first.manifest_hash == second.manifest_hash


def test_changed_script_creates_new_version_and_parent(database) -> None:
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    builder = RenderManifestBuilder(database)
    first = builder.build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PREVIEW,
        )
    )
    second = builder.build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PREVIEW,
            script_hash="f" * 64,
        )
    )
    assert second.id != first.id
    assert second.document.manifest_version == 2
    assert second.parent_manifest_id == first.id
    assert second.manifest_hash != first.manifest_hash


def test_approval_for_old_script_cannot_authorize_changed_publish(database, tmp_path: Path) -> None:
    content_id, workflow_id, asset, gate_id, review_id = _publish_context(
        database, tmp_path
    )
    with pytest.raises(ManifestValidationError, match="script_hash"):
        RenderManifestBuilder(database).build(
            build_request(
                content_id=content_id,
                workflow_id=workflow_id,
                mode=RenderMode.PUBLISH,
                asset_id=asset.id,
                rights_gate_evaluation_id=gate_id,
                approval_review_id=review_id,
                script_hash="9" * 64,
            )
        )


def test_sealed_manifest_and_asset_rows_reject_mutation(database) -> None:
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    record = RenderManifestBuilder(database).build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PREVIEW,
        )
    )
    with pytest.raises(RaiseException, match="immutable"):
        with database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.render_manifests SET platform = 'facebook' WHERE id = %s",
                (record.id,),
            )
