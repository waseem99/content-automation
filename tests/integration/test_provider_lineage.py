from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.errors import RaiseException

from src.application.assets.classification import AssetContext
from src.application.lineage.exceptions import DerivativeRegistrationError
from src.application.lineage.fingerprints import request_fingerprint
from src.application.lineage.models import DerivativeRegistrationRequest, ProviderCallCreate
from src.application.lineage.service import AssetLineageService
from src.application.manifests.builder import RenderManifestBuilder
from src.domain.asset_enums import AssetType
from src.domain.asset_models import AssetCreate
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.domain.render_status import RenderMode
from src.domain.workflow_models import StageExecutionCreate
from src.infrastructure.database.repository_provider_generation import ProviderGenerationEvidenceRepository
from src.infrastructure.database.uow import unit_of_work
from tests.integration.manifest_support import (
    build_request,
    create_approval_review,
    create_passing_gate,
    register_manifest_versions,
)
from tests.integration.rights_support import (
    approve_rights,
    close_database,
    create_workflow,
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage(database, workflow_id):
    unique = uuid4()
    with unit_of_work(database) as uow:
        return uow.stage_executions.create(
            StageExecutionCreate(
                workflow_run_id=workflow_id,
                stage_name=f"image-edit-{unique}",
                stage_version="1",
                idempotency_key=f"stage-{unique}",
                input_hash="1" * 64,
                model_or_tool="test-provider",
                prompt_version="v1",
                operator="pytest",
            )
        )


def _source_asset(database, tmp_path: Path, *, synthetic=True, modification=True):
    registry = registry_for(database, tmp_path)
    source_path = tmp_path / f"source-{uuid4()}.png"
    evidence_path = tmp_path / f"license-{uuid4()}.pdf"
    source_path.write_bytes(b"source-image")
    evidence_path.write_bytes(b"license-evidence")
    asset = register_asset(registry, source_path, AssetContext.WEB_IMAGE_SOURCE)
    rights = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence_path,
        modification=modification,
        synthetic_edit=synthetic,
        territories=["worldwide"],
        platforms=["youtube"],
    )
    return registry, asset, rights


def _request(workflow_id, stage_id, parent, output_path: Path, *, provider_request_id="req-1"):
    output_sha = _sha(output_path)
    request_hash = request_fingerprint(
        provider="openai",
        operation="image_edit",
        model_id="gpt-image-1",
        prompt_hash="a" * 64,
        input_sha256=parent.sha256,
        parameters={"size": "1024x1024"},
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
        prompt_name="cinematic_edit",
        prompt_version="v1",
        prompt_hash="a" * 64,
        provider_call=ProviderCallCreate(
            stage_execution_id=stage_id,
            provider="openai",
            operation="image_edit",
            provider_request_id=provider_request_id,
            idempotency_key=f"openai-{request_hash}",
            request_fingerprint=request_hash,
            response_fingerprint=output_sha,
            units=1,
            unit_name="image",
            cost_usd=0,
            metadata={"safe": True},
        ),
        created_by="pytest",
        metadata={"purpose": "lineage-test"},
    )


def test_derivative_registration_preserves_parent_and_provider_evidence(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    registry, parent, _ = _source_asset(database, tmp_path)
    output_path = tmp_path / "derived.png"
    output_path.write_bytes(b"derived-image")

    result = AssetLineageService(
        database=database,
        registry=registry,
        rights_gate=gate_for(database, tmp_path),
    ).register_derivative(_request(workflow_id, stage.id, parent, output_path))

    with unit_of_work(database) as uow:
        child = uow.assets.get(result.asset_id)
        evidence = ProviderGenerationEvidenceRepository(uow.conn).get_for_output_asset(child.id)
    assert child.parent_asset_id == parent.id
    assert child.source_type == AssetSourceType.AI_GENERATED
    assert evidence is not None
    assert evidence.input_asset_sha256 == parent.sha256
    assert evidence.output_asset_sha256 == child.sha256
    assert output_path.exists(), "source output file is not deleted by registration"


def test_repeated_identical_generation_reuses_existing_valid_asset(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    registry, parent, _ = _source_asset(database, tmp_path)
    output_path = tmp_path / "same.png"
    output_path.write_bytes(b"same-output")
    service = AssetLineageService(database=database, registry=registry, rights_gate=gate_for(database, tmp_path))

    first = service.register_derivative(_request(workflow_id, stage.id, parent, output_path, provider_request_id="req-a"))
    second = service.register_derivative(_request(workflow_id, stage.id, parent, output_path, provider_request_id="req-a"))

    assert second.reused is True
    assert second.asset_id == first.asset_id
    assert second.evidence_id == first.evidence_id


def test_output_hash_mismatch_does_not_register_asset_or_provider_call(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    registry, parent, _ = _source_asset(database, tmp_path)
    output_path = tmp_path / "partial.png"
    output_path.write_bytes(b"partial-output")
    request = _request(workflow_id, stage.id, parent, output_path)
    request = request.model_copy(
        update={"provider_call": request.provider_call.model_copy(update={"response_fingerprint": "f" * 64})}
    )

    with pytest.raises(DerivativeRegistrationError, match="Output bytes"):
        AssetLineageService(database=database, registry=registry, rights_gate=gate_for(database, tmp_path)).register_derivative(request)

    with unit_of_work(database) as uow:
        assert uow.assets.get_by_sha256(_sha(output_path)) is None
        rows = uow.conn.execute("SELECT * FROM football_brief.provider_calls WHERE provider_request_id = 'req-1'").fetchall()
    assert rows == []


def test_synthetic_edit_is_blocked_when_source_rights_prohibit_it(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    stage = _stage(database, workflow_id)
    registry, parent, _ = _source_asset(database, tmp_path, synthetic=False)
    output_path = tmp_path / "blocked.png"
    output_path.write_bytes(b"blocked-output")

    with pytest.raises(DerivativeRegistrationError, match="SYNTHETIC_EDIT_NOT_ALLOWED"):
        AssetLineageService(database=database, registry=registry, rights_gate=gate_for(database, tmp_path)).register_derivative(
            _request(workflow_id, stage.id, parent, output_path)
        )


def test_multigeneration_lineage_returns_source_to_render_chain(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    first_stage = _stage(database, workflow_id)
    second_stage = _stage(database, workflow_id)
    registry, parent, _ = _source_asset(database, tmp_path)
    first_output = tmp_path / "first.png"
    second_output = tmp_path / "second.png"
    first_license = tmp_path / "first-license.pdf"
    first_output.write_bytes(b"first-output")
    second_output.write_bytes(b"second-output")
    first_license.write_bytes(b"first-license")
    service = AssetLineageService(database=database, registry=registry, rights_gate=gate_for(database, tmp_path))
    first = service.register_derivative(_request(workflow_id, first_stage.id, parent, first_output, provider_request_id="req-first"))

    approve_rights(
        database=database,
        registry=registry,
        asset_id=first.asset_id,
        evidence_path=first_license,
        modification=True,
        synthetic_edit=True,
        territories=["worldwide"],
        platforms=["youtube"],
    )
    with unit_of_work(database) as uow:
        first_asset = uow.assets.get(first.asset_id)
    second = service.register_derivative(_request(workflow_id, second_stage.id, first_asset, second_output, provider_request_id="req-second"))

    report = service.lineage_for_asset(second.asset_id)
    assert [node.asset_id for node in report.nodes] == [second.asset_id, first.asset_id, parent.id]
    assert report.nodes[0].provider == "openai"
    assert report.nodes[1].provider == "openai"


def test_generated_publish_asset_requires_provider_evidence(database, tmp_path: Path) -> None:
    register_manifest_versions(database)
    workflow_id = create_workflow(database)
    registry = registry_for(database, tmp_path)
    generated_path = tmp_path / "no-evidence.png"
    license_path = tmp_path / "generated-license.pdf"
    generated_path.write_bytes(b"generated-without-evidence")
    license_path.write_bytes(b"license")
    with unit_of_work(database) as uow:
        generated = uow.assets.create(
            AssetCreate(
                asset_type=AssetType.IMAGE,
                source_type=AssetSourceType.AI_GENERATED,
                lifecycle_status=AssetLifecycleStatus.INTERNAL_ONLY,
                storage_uri=registry.storage_resolver.workspace_uri(generated_path),
                sha256=_sha(generated_path),
                created_by="pytest",
            )
        )
    approve_rights(
        database=database,
        registry=registry,
        asset_id=generated.id,
        evidence_path=license_path,
        territories=["worldwide"],
        platforms=["youtube"],
    )
    with unit_of_work(database) as uow:
        content_id = uow.workflow_runs.get(workflow_id).content_item_id
    gate_id = create_passing_gate(database, tmp_path, workflow_id, generated.id)
    review_id = create_approval_review(database, workflow_id, [generated.id])

    with pytest.raises(RaiseException, match="Generated assets require provider generation evidence"):
        RenderManifestBuilder(database).build(
            build_request(
                content_id=content_id,
                workflow_id=workflow_id,
                mode=RenderMode.PUBLISH,
                asset_id=generated.id,
                rights_gate_evaluation_id=gate_id,
                approval_review_id=review_id,
            )
        )
