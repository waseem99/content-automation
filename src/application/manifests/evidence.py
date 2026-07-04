from __future__ import annotations

from uuid import UUID

from src.application.manifests.exceptions import ManifestValidationError
from src.application.manifests.models import ManifestAssetInput, RenderManifestBuildRequest
from src.domain.render_manifest_models import (
    ManifestApprovalReference,
    ManifestAssetReference,
    ManifestDisclosure,
    RightsEvaluationReference,
)


class ManifestEvidenceLoader:
    def __init__(self, uow) -> None:
        self.uow = uow

    def validate_workflow(self, request: RenderManifestBuildRequest) -> None:
        workflow = self.uow.workflow_runs.get(request.workflow_run_id)
        if workflow.content_item_id != request.content_item_id:
            raise ManifestValidationError("Workflow does not belong to the content item")

    def load_approval(
        self,
        request: RenderManifestBuildRequest,
    ) -> ManifestApprovalReference | None:
        if request.approval_review_id is None:
            return None
        row = self.uow.conn.execute(
            "SELECT * FROM football_brief.human_reviews WHERE id = %s",
            (request.approval_review_id,),
        ).fetchone()
        if row is None:
            raise ManifestValidationError("Approval review was not found")
        if row["workflow_run_id"] != request.workflow_run_id:
            raise ManifestValidationError("Approval review belongs to another workflow")
        if row["decision"] != "approved":
            raise ManifestValidationError("Approval review is not approved")
        self._validate_approval_subject(row["checklist"] or {}, request)
        return ManifestApprovalReference(
            human_review_id=row["id"],
            reviewer=row["reviewer"],
            approved_at=row["created_at"],
        )

    def load_rights(
        self,
        request: RenderManifestBuildRequest,
    ) -> tuple[RightsEvaluationReference | None, dict[UUID, dict]]:
        if request.rights_gate_evaluation_id is None:
            return None, {}
        evaluation = self.uow.rights_gate_evaluations.get(
            request.rights_gate_evaluation_id
        )
        if evaluation is None:
            raise ManifestValidationError("Rights evaluation was not found")
        if evaluation["workflow_run_id"] != request.workflow_run_id:
            raise ManifestValidationError("Rights evaluation belongs to another workflow")
        if evaluation["outcome"] != "pass":
            raise ManifestValidationError("Rights evaluation did not pass")
        if evaluation["platform"] != request.platform.lower():
            raise ManifestValidationError("Rights evaluation platform does not match")

        decisions = self.uow.rights_gate_evaluations.list_asset_decisions(
            evaluation["id"]
        )
        decision_by_asset = {row["asset_id"]: row for row in decisions}
        return (
            RightsEvaluationReference(
                evaluation_id=evaluation["id"],
                policy_version=evaluation["policy_version"],
                policy_hash=evaluation["policy_hash"],
                territory=evaluation["territory"],
                campaign=evaluation["campaign"],
                requested_uses=tuple(evaluation["requested_uses"]),
            ),
            decision_by_asset,
        )

    def enrich_assets(
        self,
        request: RenderManifestBuildRequest,
        decision_by_asset: dict[UUID, dict],
    ) -> tuple[ManifestAssetReference, ...]:
        requested_ids = {
            item.asset_id for item in request.assets if item.asset_id is not None
        }
        if decision_by_asset and requested_ids != set(decision_by_asset):
            raise ManifestValidationError(
                "Publish manifest assets must exactly match the passing rights evaluation"
            )

        enriched: list[ManifestAssetReference] = []
        for item in request.assets:
            enriched.append(self._enrich_asset(item, decision_by_asset))
        return tuple(enriched)

    def disclosures_from_rights(
        self,
        decision_by_asset: dict[UUID, dict],
    ) -> tuple[ManifestDisclosure, ...]:
        disclosures: list[ManifestDisclosure] = []
        for asset_id, decision in sorted(
            decision_by_asset.items(), key=lambda pair: str(pair[0])
        ):
            obligations = decision.get("obligations") or {}
            attribution = obligations.get("attribution_text")
            if obligations.get("attribution_required") and attribution:
                disclosures.append(
                    ManifestDisclosure(
                        code=f"ATTRIBUTION:{asset_id}",
                        text=str(attribution),
                        required=True,
                    )
                )
        return tuple(disclosures)

    @staticmethod
    def _validate_approval_subject(
        checklist: dict,
        request: RenderManifestBuildRequest,
    ) -> None:
        expected = {
            "script_hash": request.script.content_hash,
            "storyboard_hash": request.storyboard.content_hash,
            "brand_hash": request.brand.content_hash,
            "policy_hash": request.policy.content_hash,
            "asset_ids": sorted(
                str(item.asset_id)
                for item in request.assets
                if item.asset_id is not None
            ),
        }
        for key, value in expected.items():
            if checklist.get(key) != value:
                raise ManifestValidationError(
                    f"Approval review does not match manifest input: {key}"
                )

    def _enrich_asset(
        self,
        item: ManifestAssetInput,
        decision_by_asset: dict[UUID, dict],
    ) -> ManifestAssetReference:
        if item.asset_id is None:
            return ManifestAssetReference(
                role=item.role,
                sequence_number=item.sequence_number,
                placeholder_key=item.placeholder_key,
                metadata=item.metadata,
            )

        asset = self.uow.assets.get(item.asset_id)
        decision = decision_by_asset.get(item.asset_id)
        if decision is not None:
            if decision["outcome"] != "pass":
                raise ManifestValidationError("Manifest asset rights decision did not pass")
            if decision["asset_sha256"] != asset.sha256:
                raise ManifestValidationError("Manifest asset hash differs from rights decision")
            rights_id = decision["selected_asset_rights_id"]
            evidence_ids = tuple(decision["evidence_ids"])
        else:
            rights_id = None
            evidence_ids = ()

        return ManifestAssetReference(
            asset_id=asset.id,
            asset_sha256=asset.sha256,
            asset_rights_id=rights_id,
            rights_evidence_ids=evidence_ids,
            role=item.role,
            sequence_number=item.sequence_number,
            parent_asset_id=asset.parent_asset_id,
            metadata=item.metadata,
        )
