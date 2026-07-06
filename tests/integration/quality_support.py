from __future__ import annotations

import hashlib
from pathlib import Path

from src.application.assets.classification import AssetContext
from src.application.assets.resolver import AssetResolver
from src.application.manifests.builder import RenderManifestBuilder
from src.domain.asset_enums import AssetType
from src.domain.asset_models import AssetCreate
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.domain.render_status import RenderMode
from src.infrastructure.database.uow import unit_of_work
from tests.integration.manifest_support import (
    build_request,
    create_approval_review,
    create_manifest_workflow,
    create_passing_gate,
    register_manifest_versions,
)
from tests.integration.rights_support import approve_rights, register_asset, registry_for


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_asset(database, tmp_path: Path, *, attribution_required=False):
    registry = registry_for(database, tmp_path)
    image = tmp_path / "source.png"
    evidence = tmp_path / "license.pdf"
    image.write_bytes(b"source-image")
    evidence.write_bytes(b"license")
    asset = register_asset(registry, image, AssetContext.WEB_IMAGE_SOURCE)
    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        attribution_required=attribution_required,
        attribution_text="Image by Test Licensor" if attribution_required else None,
        territories=["US", "worldwide"],
        platforms=["youtube"],
    )
    return registry, asset


def output_asset(database, registry, path: Path, *, metadata: dict | None = None):
    path.write_bytes(b"render-output")
    with unit_of_work(database) as uow:
        return uow.assets.create(
            AssetCreate(
                asset_type=AssetType.VIDEO,
                source_type=AssetSourceType.OWNED,
                lifecycle_status=AssetLifecycleStatus.APPROVED,
                storage_uri=registry.storage_resolver.workspace_uri(path),
                sha256=sha(path),
                original_filename=path.name,
                mime_type="video/mp4",
                size_bytes=path.stat().st_size,
                metadata=metadata or {
                    "media": {
                        "valid_container": True,
                        "width": 1080,
                        "height": 1920,
                        "fps": 30,
                        "duration_sec": 30,
                        "has_audio": True,
                    }
                },
                created_by="pytest",
            )
        )


def publish_manifest_and_job(database, tmp_path: Path, *, attribution_required=False, output_metadata=None):
    register_manifest_versions(database)
    content_id, workflow_id = create_manifest_workflow(database)
    registry, asset = source_asset(database, tmp_path, attribution_required=attribution_required)
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
    output = output_asset(database, registry, tmp_path / "render.mp4", metadata=output_metadata)
    with unit_of_work(database) as uow:
        job = uow.render_jobs.create(manifest.id)
        uow.render_jobs.set_running(job["id"])
        job = uow.render_jobs.set_succeeded(job["id"], output.id)
    return registry, AssetResolver(database, registry.storage_resolver), manifest, job, asset, output
