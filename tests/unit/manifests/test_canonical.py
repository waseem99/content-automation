from __future__ import annotations

from uuid import uuid4

from src.application.manifests.canonical import (
    canonical_json_bytes,
    manifest_hash,
    material_input_hash,
)
from src.domain.render_manifest_models import (
    ManifestAssetReference,
    RenderManifestDocument,
    VersionedHashReference,
)
from src.domain.render_status import ManifestAssetRole, RenderMode


def _reference(value: str) -> VersionedHashReference:
    return VersionedHashReference(version="1", content_hash=value * 64)


def _document(script_hash: str = "a") -> RenderManifestDocument:
    return RenderManifestDocument(
        content_item_id=uuid4(),
        workflow_run_id=uuid4(),
        manifest_version=1,
        mode=RenderMode.PREVIEW,
        platform="youtube",
        aspect_ratio="9:16",
        script=_reference(script_hash),
        storyboard=_reference("b"),
        brand=_reference("c"),
        policy=_reference("d"),
        assets=(
            ManifestAssetReference(
                role=ManifestAssetRole.IMAGE,
                sequence_number=0,
                placeholder_key="hero-image",
            ),
        ),
        not_for_publication=True,
        watermark_text="PREVIEW - NOT FOR PUBLICATION",
        output_metadata={"NOT_FOR_PUBLICATION": True},
    )


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes(
        {"a": 1, "b": 2}
    )


def test_manifest_hash_is_stable() -> None:
    document = _document()
    assert manifest_hash(document) == manifest_hash(document)
    assert len(manifest_hash(document)) == 64


def test_material_hash_changes_when_script_changes() -> None:
    first = _document("a")
    second = first.model_copy(
        update={"script": VersionedHashReference(version="2", content_hash="e" * 64)}
    )
    assert material_input_hash(first) != material_input_hash(second)
    assert manifest_hash(first) != manifest_hash(second)


def test_material_hash_ignores_manifest_version() -> None:
    first = _document()
    second = first.model_copy(update={"manifest_version": 2})
    assert material_input_hash(first) == material_input_hash(second)
    assert manifest_hash(first) != manifest_hash(second)
