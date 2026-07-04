from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from src.application.assets.exceptions import AssetHashMismatch, AssetStorageMissing, AssetUnavailable
from src.application.assets.resolver import AssetResolver
from src.application.rights.decision_models import AssetRightsDecision, RightsGateDecision
from src.application.rights.enums import RightsDecisionOutcome
from src.application.rights.match_footage import MatchFootageClassifier
from src.application.rights.policy import RightsPolicy, load_rights_policy
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
from src.application.rights.selection import EffectiveRightsSelector
from src.domain.asset_models import Asset
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_rights_decisions import RightsGateEvaluationRepository
from src.infrastructure.database.repository_rights_links import AssetRightsEvidenceLinkRepository
from src.infrastructure.database.repository_rights_state import RightsStateRepository
from src.infrastructure.database.repository_workflow_events import WorkflowEventRepository
from src.infrastructure.database.uow import unit_of_work


class RightsGateService:
    def __init__(
        self,
        *,
        database: Database,
        asset_resolver: AssetResolver,
        policy: RightsPolicy | None = None,
        policy_path: Path = Path("policies/rights-gate/v1.json"),
    ) -> None:
        self.database = database
        self.asset_resolver = asset_resolver
        self.policy = policy or load_rights_policy(policy_path)
        self.selector = EffectiveRightsSelector(self.policy)

    def evaluate(
        self,
        request: RightsGateRequest,
        *,
        now: datetime | None = None,
    ) -> RightsGateDecision:
        evaluated_at = now or datetime.now(timezone.utc)
        decisions = tuple(
            self._evaluate_asset(asset_id, request, evaluated_at)
            for asset_id in request.asset_ids
        )
        outcome = self._aggregate_outcome(decisions)
        reasons = self._aggregate_reasons(decisions)
        fingerprint = self._fingerprint(request, decisions)
        obligations = {
            str(decision.asset_id): decision.obligations.model_dump(mode="json")
            for decision in decisions
            if decision.obligations.attribution_required or decision.obligations.disclosures
        }

        with unit_of_work(self.database) as uow:
            repository = RightsGateEvaluationRepository(uow.conn)
            evaluation = repository.create(
                request=request,
                policy_version=self.policy.version,
                policy_hash=self.policy.content_hash,
                evaluation_fingerprint=fingerprint,
                outcome=outcome.value,
                reason_codes=tuple(reason.value for reason in reasons),
                obligations=obligations,
                evaluated_at=evaluated_at,
            )
            for decision in decisions:
                repository.add_asset_decision(
                    evaluation_id=evaluation["id"],
                    decision=decision,
                    evaluated_at=evaluated_at,
                )
            self._record_workflow_effect(uow.conn, request, evaluation["id"], outcome, reasons)

        return RightsGateDecision(
            evaluation_id=evaluation["id"],
            outcome=outcome,
            asset_decisions=decisions,
            reason_codes=reasons,
            policy_version=self.policy.version,
            policy_hash=self.policy.content_hash,
            evaluated_at=evaluated_at,
        )

    def _evaluate_asset(
        self,
        asset_id: UUID,
        request: RightsGateRequest,
        now: datetime,
    ) -> AssetRightsDecision:
        with unit_of_work(self.database) as uow:
            asset = uow.assets.get(asset_id)
            records = RightsStateRepository(uow.conn).list_unsuperseded_for_asset(asset_id)
            links = AssetRightsEvidenceLinkRepository(uow.conn)
            evidence = {record.id: links.evidence_ids(record.id) for record in records}
            ancestors = self._ancestors(uow, asset)

        try:
            self.asset_resolver.resolve(asset_id, verify_hash=True)
        except AssetHashMismatch:
            return self._hard_failure(asset, RightsReasonCode.ASSET_HASH_MISMATCH)
        except (AssetStorageMissing, AssetUnavailable):
            return self._hard_failure(asset, RightsReasonCode.ASSET_UNAVAILABLE)

        return self.selector.select(
            asset=asset,
            records=records,
            evidence_by_rights=evidence,
            request=request,
            now=now,
            is_match_footage=MatchFootageClassifier.is_match_footage(asset, ancestors),
        )

    @staticmethod
    def _ancestors(uow, asset: Asset) -> tuple[Asset, ...]:
        result: list[Asset] = []
        current = asset
        seen: set[UUID] = set()
        while current.parent_asset_id is not None and current.parent_asset_id not in seen:
            seen.add(current.parent_asset_id)
            parent = uow.assets.get_optional(current.parent_asset_id)
            if parent is None:
                break
            result.append(parent)
            current = parent
            if len(result) >= 32:
                break
        return tuple(result)

    @staticmethod
    def _hard_failure(asset: Asset, reason: RightsReasonCode) -> AssetRightsDecision:
        return AssetRightsDecision(
            asset_id=asset.id,
            asset_sha256=asset.sha256,
            outcome=RightsDecisionOutcome.BLOCK,
            reason_codes=(reason,),
        )

    @staticmethod
    def _aggregate_outcome(
        decisions: tuple[AssetRightsDecision, ...],
    ) -> RightsDecisionOutcome:
        if any(item.outcome == RightsDecisionOutcome.BLOCK for item in decisions):
            return RightsDecisionOutcome.BLOCK
        if any(
            item.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED
            for item in decisions
        ):
            return RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED
        return RightsDecisionOutcome.PASS

    def _aggregate_reasons(
        self,
        decisions: tuple[AssetRightsDecision, ...],
    ) -> tuple[RightsReasonCode, ...]:
        reasons = {reason for decision in decisions for reason in decision.reason_codes}
        return tuple(
            sorted(
                reasons,
                key=lambda item: (self.policy.priority(item.value), item.value),
            )
        )

    def _fingerprint(
        self,
        request: RightsGateRequest,
        decisions: tuple[AssetRightsDecision, ...],
    ) -> str:
        payload = {
            "request": request.model_dump(mode="json"),
            "policy_hash": self.policy.content_hash,
            "assets": [decision.model_dump(mode="json") for decision in decisions],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_workflow_effect(
        conn,
        request: RightsGateRequest,
        evaluation_id: UUID,
        outcome: RightsDecisionOutcome,
        reasons: tuple[RightsReasonCode, ...],
    ) -> None:
        event_repository = WorkflowEventRepository(conn)
        event_repository.create(
            workflow_run_id=request.workflow_run_id,
            stage_execution_id=request.stage_execution_id,
            event_type="rights_gate_evaluated",
            actor=request.evaluated_by,
            reason=outcome.value,
            payload={
                "evaluation_id": str(evaluation_id),
                "gate_point": request.gate_point.value,
                "reason_codes": [reason.value for reason in reasons],
            },
            to_status="blocked" if outcome == RightsDecisionOutcome.BLOCK else None,
        )
        if outcome == RightsDecisionOutcome.BLOCK:
            conn.execute(
                """
                UPDATE football_brief.workflow_runs
                SET status = 'blocked', failure_reason = %s
                WHERE id = %s
                """,
                (",".join(reason.value for reason in reasons), request.workflow_run_id),
            )
        elif (
            outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED
            and request.stage_execution_id is not None
        ):
            conn.execute(
                """
                UPDATE football_brief.stage_executions
                SET status = 'awaiting_human'
                WHERE id = %s
                """,
                (request.stage_execution_id,),
            )
