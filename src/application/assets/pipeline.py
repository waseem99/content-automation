from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.models import AssetHandle, RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService


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
    source_result = registry.register_file(
        RegisterFileRequest(
            path=source_video,
            asset_type=source_classification.asset_type,
            source_type=source_classification.source_type,
            lifecycle_status=source_classification.lifecycle_status,
            storage_mode=StorageMode.REFERENCE_IN_PLACE,
            created_by=created_by,
            metadata={"pipeline_role": "source_match_video"},
        )
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    clip_entries = {entry.get("file"): entry for entry in manifest.get("clips", [])}
    clip_classification = policy.classify(AssetContext.EXTRACTED_MATCH_CLIP)
    for clip_path in clip_paths:
        result = registry.register_file(
            RegisterFileRequest(
                path=clip_path,
                asset_type=clip_classification.asset_type,
                source_type=clip_classification.source_type,
                lifecycle_status=clip_classification.lifecycle_status,
                storage_mode=StorageMode.REFERENCE_IN_PLACE,
                parent_asset_id=source_result.asset.id,
                created_by=created_by,
                metadata={"pipeline_role": "extracted_match_clip"},
            )
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
    source = registry.register_file(
        RegisterFileRequest(
            path=original_path,
            asset_type=source_classification.asset_type,
            source_type=source_classification.source_type,
            lifecycle_status=source_classification.lifecycle_status,
            storage_mode=StorageMode.COPY_TO_MANAGED_STORE,
            created_by=created_by,
            metadata={"pipeline_role": "web_image_source", **(metadata or {})},
        )
    )
    derivative_classification = policy.classify(AssetContext.WEB_IMAGE_DERIVATIVE)
    derivative = registry.register_file(
        RegisterFileRequest(
            path=normalized_path,
            asset_type=derivative_classification.asset_type,
            source_type=derivative_classification.source_type,
            lifecycle_status=derivative_classification.lifecycle_status,
            storage_mode=StorageMode.REFERENCE_IN_PLACE,
            parent_asset_id=source.asset.id,
            created_by=created_by,
            metadata={"pipeline_role": "web_image_derivative", **(metadata or {})},
        )
    )
    return (
        AssetHandle(source.asset.id, source.inspected_path),
        AssetHandle(derivative.asset.id, derivative.inspected_path),
    )
