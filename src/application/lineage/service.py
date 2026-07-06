from __future__ import annotations

from src.application.assets.exceptions import FileChangedDuringHashing
from src.application.assets.models import RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.application.lineage.exceptions import DerivativeRegistrationError, ProviderCallError
from src.application.lineage.models import DerivativeRegistrationRequest, DerivativeRegistrationResult
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.gate import RightsGateService
from src.application.rights.request_models import RightsGateRequest
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.domain.provider_lineage_models import ProviderGenerationEvidenceCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_provider_generation import ProviderGenerationEvidenceRepository
from src.infrastructure.database.uow import unit_of_work


class AssetLineageService:
    def __init__(self, *, database: Database, registry: AssetRegistryService, rights_gate: RightsGateService) -> None:
        self.database = database
        self.registry = registry
        self.rights_gate = rights_gate

    def register_derivative(self, request: DerivativeRegistrationRequest) -> DerivativeRegistrationResult:
        parent = self._load_parent(request)
        self._verify_derivative_rights(request)
        with unit_of_work(self.database) as uow:
            existing = ProviderGenerationEvidenceRepository(uow.conn).find_reusable(
                provider=request.provider,
                operation=request.operation,
                request_fingerprint=request.provider_call.request_fingerprint,
                input_asset_sha256=parent.sha256,
            )
            if existing is not None and request.allow_reuse:
                return DerivativeRegistrationResult(
                    asset_id=existing.output_asset_id,
                    evidence_id=existing.id,
                    reused=True,
                )

        inspection = self.registry.inspect(
            RegisterFileRequest(
                path=request.output_path,
                asset_type=request.output_asset_type,
                source_type=AssetSourceType.AI_GENERATED,
                lifecycle_status=AssetLifecycleStatus.INTERNAL_ONLY,
                storage_mode=StorageMode.COPY_TO_MANAGED_STORE,
                parent_asset_id=request.parent_asset_id,
                created_by=request.created_by,
                metadata=request.metadata,
            )
        )
        if inspection.sha256 != request.provider_call.response_fingerprint:
            raise DerivativeRegistrationError("Output bytes do not match provider response fingerprint")

        with unit_of_work(self.database) as uow:
            provider_call_id = self._create_provider_call(uow.conn, request)
            registered = self.registry.register_inspection_in_uow(
                uow,
                RegisterFileRequest(
                    path=request.output_path,
                    asset_type=request.output_asset_type,
                    source_type=AssetSourceType.AI_GENERATED,
                    lifecycle_status=AssetLifecycleStatus.INTERNAL_ONLY,
                    storage_mode=StorageMode.COPY_TO_MANAGED_STORE,
                    parent_asset_id=request.parent_asset_id,
                    created_by=request.created_by,
                    metadata={
                        **request.metadata,
                        "provider": request.provider,
                        "operation": request.operation,
                        "model_id": request.model_id,
                        "prompt_hash": request.prompt_hash,
                        "request_fingerprint": request.provider_call.request_fingerprint,
                    },
                ),
                inspection,
            )
            evidence = ProviderGenerationEvidenceRepository(uow.conn).create(
                ProviderGenerationEvidenceCreate(
                    provider_call_id=provider_call_id,
                    output_asset_id=registered.asset.id,
                    parent_asset_id=request.parent_asset_id,
                    workflow_run_id=request.workflow_run_id,
                    stage_execution_id=request.stage_execution_id,
                    provider=request.provider,
                    operation=request.operation,
                    model_id=request.model_id,
                    prompt_name=request.prompt_name,
                    prompt_version=request.prompt_version,
                    prompt_hash=request.prompt_hash,
                    request_fingerprint=request.provider_call.request_fingerprint,
                    response_fingerprint=request.provider_call.response_fingerprint,
                    provider_request_id=request.provider_call.provider_request_id,
                    input_asset_sha256=parent.sha256,
                    output_asset_sha256=registered.asset.sha256,
                    metadata=request.metadata,
                )
            )
            uow.workflow_events.create(
                workflow_run_id=request.workflow_run_id,
                stage_execution_id=request.stage_execution_id,
                event_type="provider_generation_registered",
                actor=request.created_by,
                reason=request.operation,
                payload={
                    "output_asset_id": str(registered.asset.id),
                    "parent_asset_id": str(request.parent_asset_id),
                    "provider": request.provider,
                    "model_id": request.model_id,
                    "provider_generation_evidence_id": str(evidence.id),
                },
            )
            return DerivativeRegistrationResult(asset_id=registered.asset.id, evidence_id=evidence.id, reused=False)

    def lineage_for_asset(self, asset_id):
        with unit_of_work(self.database) as uow:
            return ProviderGenerationEvidenceRepository(uow.conn).lineage_for_asset(asset_id)

    def _load_parent(self, request: DerivativeRegistrationRequest):
        with unit_of_work(self.database) as uow:
            parent = uow.assets.get_optional(request.parent_asset_id)
            stage = uow.stage_executions.get(request.stage_execution_id)
        if parent is None:
            raise DerivativeRegistrationError("Parent asset does not exist")
        if stage.workflow_run_id != request.workflow_run_id:
            raise DerivativeRegistrationError("Stage execution does not belong to workflow")
        return parent

    def _verify_derivative_rights(self, request: DerivativeRegistrationRequest) -> None:
        decision = self.rights_gate.evaluate(
            RightsGateRequest(
                workflow_run_id=request.workflow_run_id,
                stage_execution_id=request.stage_execution_id,
                gate_point=RightsGatePoint.MANIFEST_ADMISSION,
                asset_ids=(request.parent_asset_id,),
                platform=RightsPlatform(request.platform.strip().lower()),
                territory=request.territory,
                campaign=request.campaign,
                commercial_use=True,
                editorial_use=True,
                modification=request.require_modification_rights,
                synthetic_edit=request.require_synthetic_edit_rights,
                evaluated_by=request.created_by,
            )
        )
        if decision.outcome != RightsDecisionOutcome.PASS:
            raise DerivativeRegistrationError(
                "Source asset rights do not allow derivative generation: "
                + ",".join(reason.value for reason in decision.reason_codes)
            )

    @staticmethod
    def _create_provider_call(conn, request: DerivativeRegistrationRequest):
        row = conn.execute(
            """
            INSERT INTO football_brief.provider_calls (
                stage_execution_id, provider, operation, provider_request_id,
                idempotency_key, status, request_fingerprint,
                response_fingerprint, units, unit_name, cost_usd,
                completed_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, 'succeeded', %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (provider, idempotency_key) DO UPDATE SET
                provider_request_id = EXCLUDED.provider_request_id,
                status = EXCLUDED.status,
                response_fingerprint = EXCLUDED.response_fingerprint,
                units = EXCLUDED.units,
                unit_name = EXCLUDED.unit_name,
                cost_usd = EXCLUDED.cost_usd,
                completed_at = EXCLUDED.completed_at,
                metadata = EXCLUDED.metadata
            RETURNING id, status
            """,
            (
                request.stage_execution_id,
                request.provider,
                request.operation,
                request.provider_call.provider_request_id,
                request.provider_call.idempotency_key,
                request.provider_call.request_fingerprint,
                request.provider_call.response_fingerprint,
                request.provider_call.units,
                request.provider_call.unit_name,
                request.provider_call.cost_usd,
                request.provider_call.metadata,
            ),
        ).fetchone()
        if row is None or row["status"] != "succeeded":
            raise ProviderCallError("Provider call was not recorded as succeeded")
        return row["id"]
