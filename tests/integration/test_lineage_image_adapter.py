from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from src.application.assets.resolver import AssetResolver
from src.application.lineage.exceptions import DerivativeRegistrationError
from src.application.lineage.fingerprints import request_fingerprint
from src.application.lineage.models import DerivativeRegistrationRequest, ProviderCallCreate
from src.application.lineage.provider_image_adapter import LineageAwareImageAdapter
from src.application.lineage.service import AssetLineageService
from src.domain.asset_enums import AssetType
from tests.integration.rights_support import (
    close_database,
    create_workflow,
    database_fixture,
    gate_for,
    registry_for,
)
from tests.integration.test_provider_lineage import _source_asset, _stage


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _adapter(database, tmp_path: Path):
    registry = registry_for(database, tmp_path)
    resolver = AssetResolver(database, registry.storage_resolver)
    lineage = AssetLineageService(
        database=database,
        registry=registry,
        rights_gate=gate_for(database, tmp_path),
    )
    return LineageAwareImageAdapter(resolver=resolver, lineage=lineage), registry


def _request(workflow_id, stage_id, parent, output_path: Path, output_bytes: bytes):
    request_hash = request_fingerprint(
        provider="openai",
        operation="image_edit",
        model_id="gpt-image-1",
        prompt_hash="b" * 64,
        input_sha256=parent.sha256,
        parameters={"adapter": True},
    )
    return DerivativeRegistrationRequest(
        workflow_run_id=workflow_id,
        stage_execution_id=stage_id,
        parent_asset_id=parent.id,
        output_path=output_path,
        output_asset_type=AssetType.IMAGE,
        provider="openai",
        operation="image_edit",
        model_id="gpt-image-1",
        prompt_name="adapter_edit",
        prompt_version="v1",
        prompt_hash="b" * 64,
        provider_call=ProviderCallCreate(
            stage_execution_id=stage_id,
            provider="openai",
            operation="image_edit",
            provider_request_id=f"adapter-{uuid4()}",
            idempotency_key=f"adapter-{request_hash}",
            request_fingerprint=request_hash,
            response_fingerprint=_sha_bytes(output_bytes),
            metadata={"adapter": True},
        ),
        created_by="pytest",
    )


def test_adapter_creates_derivative_without_touching_source(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    adapter, _ = _adapter(database, tmp_path)
    _, parent, _ = _source_asset(database, tmp_path)
    output_bytes = b"adapter-output"
    output_path = tmp_path / "adapter-output.png"

    result = adapter.edit_registered_parent(
        _request(workflow_id, stage.id, parent, output_path, output_bytes),
        lambda _source, destination: destination.write_bytes(output_bytes),
    )

    assert result.reused is False
    assert output_path.exists()


def test_adapter_rejects_overwrite_of_source_path(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    adapter, _ = _adapter(database, tmp_path)
    _, parent, _ = _source_asset(database, tmp_path)
    parent_path = adapter.resolver.resolve(parent.id).path

    with pytest.raises(DerivativeRegistrationError, match="overwrite"):
        adapter.edit_registered_parent(
            _request(workflow_id, stage.id, parent, parent_path, b"bad"),
            lambda _source, destination: destination.write_bytes(b"bad"),
        )


def test_adapter_rejects_provider_callback_that_modifies_source(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    adapter, _ = _adapter(database, tmp_path)
    _, parent, _ = _source_asset(database, tmp_path)
    output_bytes = b"adapter-output"
    output_path = tmp_path / "provider-output.png"

    def bad_callback(source: Path, destination: Path) -> None:
        source.write_bytes(b"modified-source")
        destination.write_bytes(output_bytes)

    with pytest.raises(DerivativeRegistrationError, match="modified the source"):
        adapter.edit_registered_parent(
            _request(workflow_id, stage.id, parent, output_path, output_bytes),
            bad_callback,
        )
