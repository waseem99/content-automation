from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.models import AssetHandle, RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.infrastructure.database.uow import unit_of_work


def register_extraction_manifest(
    *,
    manifest_path: Path,
    source_video: Path,
    clip_paths: list[Path],
    registry: AssetRegistryService,
    created_by: str | None = None,
) -> dict:
    policy = AssetClassificationPolicy()
    source_classification = policy.classify(AssetContext.SOURCE_MATCH_VIDEO)
    source_request = RegisterFileRequest(
        path=source_video,
        asset_type=source_classification.asset_type,
        source_type=source_classification.source_type,
        lifecycle_status=source_classification.lifecycle_status,
        storage_mode=StorageMode.REFERENCE_IN_PLACE,
        created_by=created_by,
        metadata={"pipeline_role": "source_match_video"},
    )
    source_inspection = registry.inspect(source_request)

    clip_classification = policy.classify(AssetContext.EXTRACTED_MATCH_CLIP)
    clip_requests: list[tuple[Path, RegisterFileRequest]] = []
    for clip_path in clip_paths:
        clip_requests.append(
            (
                clip_path,
                RegisterFileRequest(
                    path=clip_path,
                    asset_type=clip_classification.asset_type,
                    source_type=clip_classification.source_type,
                    lifecycle_status=clip_classification.lifecycle_status,
                    storage_mode=StorageMode.REFERENCE_IN_PLACE,
                    created_by=created_by,
                    metadata={"pipeline_role": "extracted_match_clip"},
                ),
            )
        )
    clip_inspections = {
        path: registry.inspect(request)
        for path, request in clip_requests
    }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    clip_entries = {entry.get("file"): entry for entry in manifest.get("clips", [])}

    with unit_of_work(registry.database) as uow:
        source_result = registry.register_inspection_in_uow(
            uow,
            source_request,
            source_inspection,
        )
        for clip_path, request in clip_requests:
            child_request = RegisterFileRequest(
                path=request.path,
                asset_type=request.asset_type,
                source_type=request.source_type,
                lifecycle_status=request.lifecycle_status,
                storage_mode=request.storage_mode,
                parent_asset_id=source_result.asset.id,
                created_by=request.created_by,
                metadata=request.metadata,
            )
            result = registry.register_inspection_in_uow(
                uow,
                child_request,
                clip_inspections[clip_path],
            )
            entry = clip_entries.get(clip_path.name)
            if entry is not None:
                entry["asset_id"] = str(result.asset.id)
                entry["parent_asset_id"] = str(source_result.asset.id)

    manifest["source_asset_id"] = str(source_result.asset.id)
    manifest["registry_status"] = "registered"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def register_web_image_pair(
    *,
    original_path: Path,
    normalized_path: Path,
    registry: AssetRegistryService,
    metadata: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> tuple[AssetHandle, AssetHandle]:
    policy = AssetClassificationPolicy()
    source_classification = policy.classify(AssetContext.WEB_IMAGE_SOURCE)
    source_request = RegisterFileRequest(
        path=original_path,
        asset_type=source_classification.asset_type,
        source_type=source_classification.source_type,
        lifecycle_status=source_classification.lifecycle_status,
        storage_mode=StorageMode.COPY_TO_MANAGED_STORE,
        created_by=created_by,
        metadata={"pipeline_role": "web_image_source", **(metadata or {})},
    )
    source_inspection = registry.inspect(source_request)

    derivative_classification = policy.classify(AssetContext.WEB_IMAGE_DERIVATIVE)
    derivative_request = RegisterFileRequest(
        path=normalized_path,
        asset_type=derivative_classification.asset_type,
        source_type=derivative_classification.source_type,
        lifecycle_status=derivative_classification.lifecycle_status,
        storage_mode=StorageMode.REFERENCE_IN_PLACE,
        created_by=created_by,
        metadata={"pipeline_role": "web_image_derivative", **(metadata or {})},
    )
    derivative_inspection = registry.inspect(derivative_request)

    with unit_of_work(registry.database) as uow:
        source = registry.register_inspection_in_uow(
            uow,
            source_request,
            source_inspection,
        )
        child_request = RegisterFileRequest(
            path=derivative_request.path,
            asset_type=derivative_request.asset_type,
            source_type=derivative_request.source_type,
            lifecycle_status=derivative_request.lifecycle_status,
            storage_mode=derivative_request.storage_mode,
            parent_asset_id=source.asset.id,
            created_by=derivative_request.created_by,
            metadata=derivative_request.metadata,
        )
        derivative = registry.register_inspection_in_uow(
            uow,
            child_request,
            derivative_inspection,
        )

    return (
        AssetHandle(source.asset.id, source.inspected_path),
        AssetHandle(derivative.asset.id, derivative.inspected_path),
    )
