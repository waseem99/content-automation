from __future__ import annotations

from pathlib import Path
from uuid import UUID

from src.application.manifests.models import (
    ManifestAssetInput,
    RenderManifestBuildRequest,
)
from src.application.rights.enums import RightsGatePoint, RightsPlatform
from src.application.rights.request_models import RightsGateRequest
from src.domain.render_manifest_models import VersionedHashReference
from src.domain.render_status import ManifestAssetRole, RenderMode
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import create_workflow, gate_for


BRAND_HASH = "b" * 64
POLICY_HASH = "c" * 64
SCRIPT_HASH = "d" * 64
STORYBOARD_HASH = "e" * 64


def register_manifest_versions(database) -> None:
    with database.transaction() as conn:
        conn.execute(
            """
            INSERT INTO football_brief.brand_versions (
                brand_name, version, content_hash, storage_uri, active, created_by
            ) VALUES ('football-brief', '1.0.0', %s, 'workspace:///brand.json', true, 'pytest')
            """,
            (BRAND_HASH,),
        )
        conn.execute(
            """
            INSERT INTO football_brief.policy_versions (
                policy_name, version, content_hash, storage_uri,
                effective_from, active, created_by
            ) VALUES (
                'render-policy', '1.0.0', %s, 'workspace:///policy.json',
                now(), true, 'pytest'
            )
            """,
            (POLICY_HASH,),
        )


def create_manifest_workflow(database) -> tuple[UUID, UUID]:
    workflow_id = create_workflow(database)
    with unit_of_work(database) as uow:
        workflow = uow.workflow_runs.get(workflow_id)
    return workflow.content_item_id, workflow_id


def create_approval_review(database, workflow_id: UUID) -> UUID:
    with database.transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO football_brief.human_reviews (
                workflow_run_id, review_type, decision, reviewer, rationale, checklist
            ) VALUES (
                %s, 'render_manifest', 'approved', 'pytest-reviewer',
                'Approved for publish manifest', '{"approved":true}'::jsonb
            ) RETURNING id
            """,
            (workflow_id,),
        ).fetchone()
    return row["id"]


def create_passing_gate(database, root: Path, workflow_id: UUID, asset_id: UUID) -> UUID:
    decision = gate_for(database, root).evaluate(
        RightsGateRequest(
            workflow_run_id=workflow_id,
            gate_point=RightsGatePoint.MANIFEST_ADMISSION,
            asset_ids=(asset_id,),
            platform=RightsPlatform.YOUTUBE,
            territory="US",
            commercial_use=True,
            modification=True,
            evaluated_by="pytest",
        )
    )
    return decision.evaluation_id


def build_request(
    *,
    content_id: UUID,
    workflow_id: UUID,
    mode: RenderMode,
    asset_id: UUID | None = None,
    rights_gate_evaluation_id: UUID | None = None,
    approval_review_id: UUID | None = None,
    script_hash: str = SCRIPT_HASH,
) -> RenderManifestBuildRequest:
    if asset_id is None:
        assets = (
            ManifestAssetInput(
                role=ManifestAssetRole.IMAGE,
                sequence_number=0,
                placeholder_key="hero-image",
            ),
        )
    else:
        assets = (
            ManifestAssetInput(
                asset_id=asset_id,
                role=ManifestAssetRole.IMAGE,
                sequence_number=0,
            ),
        )
    return RenderManifestBuildRequest(
        content_item_id=content_id,
        workflow_run_id=workflow_id,
        mode=mode,
        platform="youtube",
        aspect_ratio="9:16",
        script=VersionedHashReference(version="1.0.0", content_hash=script_hash),
        storyboard=VersionedHashReference(
            version="1.0.0", content_hash=STORYBOARD_HASH
        ),
        brand=VersionedHashReference(version="1.0.0", content_hash=BRAND_HASH),
        policy=VersionedHashReference(version="1.0.0", content_hash=POLICY_HASH),
        assets=assets,
        rights_gate_evaluation_id=rights_gate_evaluation_id,
        approval_review_id=approval_review_id,
        created_by="pytest",
    )
