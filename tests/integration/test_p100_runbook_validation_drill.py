from __future__ import annotations

import psycopg
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import EvidenceCategory, OperationsEvidenceRequest
from src.application.acceptance.validated_service import (
    P100_RUNBOOK_RELATIVE_PATH,
    p100_runbook_sha256,
)
from src.operations import (
    DrillCompleteRequest,
    DrillStartRequest,
    OperationsDrillKind,
    OperationsDrillStatus,
    OperationsEnvironment,
    OperationsService,
)
from tests.integration.p89_script_support import p89_database, p89_seeded


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def resolve_runbook_evidence(database, drill_id) -> dict:
    service = AcceptancePilotService(database)
    request = OperationsEvidenceRequest(
        category=EvidenceCategory.RUNBOOK_VALIDATION,
        subject_type="operations_drill_run",
        subject_id=str(drill_id),
    )
    with database.connection() as conn:
        return service._resolve_operations_evidence(conn, request)


def complete_runbook_drill(service, drill_id, *, digest: str, actor: str) -> dict:
    return service.complete_drill(
        drill_id=drill_id,
        request=DrillCompleteRequest(
            status=OperationsDrillStatus.PASSED,
            evidence={
                "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                "runbook_sha256": digest,
                "operator_profile": "non_developer",
                "checklist_completed": True,
                "validation_notes": "A non-developer completed every stop condition and evidence step.",
            },
        ),
        actor=actor,
    )


def test_runbook_acceptance_requires_explicit_current_digest_drill(
    p89_database,
    p89_seeded,
) -> None:
    operations = OperationsService(p89_database)
    actor = str(p89_seeded["admin"])

    unrelated = operations.start_drill(
        DrillStartRequest(
            environment=OperationsEnvironment.STAGING,
            drill_kind=OperationsDrillKind.STAGING_RECREATE,
        ),
        actor=actor,
    )["drill"]
    operations.complete_drill(
        drill_id=unrelated["id"],
        request=DrillCompleteRequest(
            status=OperationsDrillStatus.PASSED,
            evidence={"staging_recreated": True},
        ),
        actor=actor,
    )
    assert resolve_runbook_evidence(p89_database, unrelated["id"])["passed"] is False

    malformed = operations.start_drill(
        DrillStartRequest(
            environment=OperationsEnvironment.STAGING,
            drill_kind=OperationsDrillKind.RUNBOOK_VALIDATION,
        ),
        actor=actor,
    )["drill"]
    with pytest.raises(psycopg.Error, match="Passed runbook validation requires"):
        operations.complete_drill(
            drill_id=malformed["id"],
            request=DrillCompleteRequest(
                status=OperationsDrillStatus.PASSED,
                evidence={
                    "runbook_path": P100_RUNBOOK_RELATIVE_PATH,
                    "runbook_sha256": "a" * 64,
                    "operator_profile": "developer",
                    "checklist_completed": True,
                },
            ),
            actor=actor,
        )

    stale = operations.start_drill(
        DrillStartRequest(
            environment=OperationsEnvironment.STAGING,
            drill_kind=OperationsDrillKind.RUNBOOK_VALIDATION,
        ),
        actor=actor,
    )["drill"]
    stale_result = complete_runbook_drill(
        operations,
        stale["id"],
        digest="0" * 64,
        actor=actor,
    )
    assert stale_result["ok"] is True
    assert resolve_runbook_evidence(p89_database, stale["id"])["passed"] is False

    current = operations.start_drill(
        DrillStartRequest(
            environment=OperationsEnvironment.STAGING,
            drill_kind=OperationsDrillKind.RUNBOOK_VALIDATION,
        ),
        actor=actor,
    )["drill"]
    current_result = complete_runbook_drill(
        operations,
        current["id"],
        digest=p100_runbook_sha256(),
        actor=actor,
    )
    assert current_result["ok"] is True

    resolved = resolve_runbook_evidence(p89_database, current["id"])
    assert resolved["passed"] is True
    assert resolved["subject_id"] == str(current["id"])
    assert resolved["details"]["drill_kind"] == "runbook_validation"
    assert resolved["details"]["evidence"]["runbook_sha256"] == p100_runbook_sha256()
