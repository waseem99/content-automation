from __future__ import annotations

from pathlib import Path

import pytest
from psycopg.errors import RaiseException

from src.application.assets.classification import AssetContext
from src.application.assets.exceptions import AssetHashMismatch
from src.application.assets.resolver import AssetResolver
from src.application.manifests.builder import RenderManifestBuilder
from src.application.manifests.integrity import ManifestIntegrityVerifier
from src.application.manifests.renderer import ManifestRendererAdapter
from src.application.rights.enforcement import RenderStartGuard
from src.application.rights.exceptions import RightsGateBlocked
from src.application.rights.status import RightsStatusService
from src.domain.render_status import RenderMode
from src.infrastructure.database.uow import unit_of_work
from tests.integration.manifest_support import (
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
    gate_for,
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


def _adapter(database, tmp_path: Path) -> ManifestRendererAdapter:
    registry = registry_for(database, tmp_path)
    resolver = AssetResolver(database, registry.storage_resolver)
    return ManifestRendererAdapter(
        database=database,
        integrity=ManifestIntegrityVerifier(database, resolver),
        render_start_guard=RenderStartGuard(gate_for(database, tmp_path)),
    )


def _publish_manifest(database, tmp_path: Path):
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "render.png"
    evidence = tmp_path / "evidence" / "render-license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"render-image")
    evidence.write_bytes(b"render-evidence")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    rights = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        territories=["US"],
    )
    gate_id = create_passing_gate(database, tmp_path, workflow_id, asset.id)
    review_id = create_approval_review(database, workflow_id, [asset.id])
    manifest = RenderManifestBuilder(database).build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PUBLISH,
            asset_id=asset.id,
            rights_gate_evaluation_id=gate_id,
            approval_review_id=review_id,
        )
    )
    return manifest, media, rights


def test_renderer_receives_manifest_context(database, tmp_path: Path) -> None:
    manifest, _, _ = _publish_manifest(database, tmp_path)
    observed = {}

    def renderer(context):
        observed["manifest_id"] = context.manifest_id
        observed["paths"] = context.resolved_asset_paths
        observed["mode"] = context.mode.value
        return None

    job = _adapter(database, tmp_path).start(manifest.id, renderer)
    assert observed["manifest_id"] == manifest.id
    assert observed["mode"] == "publish"
    assert observed["paths"]
    assert job["status"] == "succeeded"
    assert job["not_for_publication"] is False


def test_asset_tamper_blocks_before_callback(database, tmp_path: Path) -> None:
    manifest, media, _ = _publish_manifest(database, tmp_path)
    media.write_bytes(b"tampered-after-approval")
    called = False

    def renderer(context):
        nonlocal called
        called = True
        return None

    with pytest.raises(AssetHashMismatch):
        _adapter(database, tmp_path).start(manifest.id, renderer)
    assert called is False


def test_revoked_rights_block_before_callback(database, tmp_path: Path) -> None:
    manifest, _, rights = _publish_manifest(database, tmp_path)
    RightsStatusService(database).revoke(rights.id, "withdrawn before render")
    called = False

    def renderer(context):
        nonlocal called
        called = True
        return None

    with pytest.raises(RightsGateBlocked):
        _adapter(database, tmp_path).start(manifest.id, renderer)
    assert called is False


def test_preview_job_cannot_enter_release_reference(database, tmp_path: Path) -> None:
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    manifest = RenderManifestBuilder(database).build(
        build_request(
            content_id=content_id,
            workflow_id=workflow_id,
            mode=RenderMode.PREVIEW,
        )
    )
    job = _adapter(database, tmp_path).start(manifest.id, lambda context: None)
    assert job["not_for_publication"] is True
    assert job["watermark_text"] == "PREVIEW - NOT FOR PUBLICATION"

    with pytest.raises(RaiseException, match="cannot enter"):
        with unit_of_work(database) as uow:
            uow.release_references.create(
                manifest_id=manifest.id,
                render_job_id=job["id"],
                package_hash="a" * 64,
                created_by="pytest",
            )


def test_publish_job_can_create_release_reference(database, tmp_path: Path) -> None:
    manifest, _, _ = _publish_manifest(database, tmp_path)
    job = _adapter(database, tmp_path).start(manifest.id, lambda context: None)
    with unit_of_work(database) as uow:
        reference = uow.release_references.create(
            manifest_id=manifest.id,
            render_job_id=job["id"],
            package_hash="f" * 64,
            created_by="pytest",
        )
    assert reference["render_manifest_id"] == manifest.id
