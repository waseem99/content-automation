from __future__ import annotations

import psycopg
import pytest

from src.application.acceptance import AcceptancePilotService
from src.application.acceptance.models import (
    PilotCreateRequest,
    PilotItemRequest,
    ProductionMode,
    SignoffDecision,
    SignoffRequest,
    SignoffRole,
)
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.test_p100_acceptance_foundation import seed_pilot_contents


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def test_reviewer_signoff_requires_assignment_to_every_pilot_brand(
    p89_database,
    p89_seeded,
) -> None:
    ready = seed_pilot_contents(p89_database, p89_seeded)
    service = AcceptancePilotService(p89_database)
    pilot = service.create(
        PilotCreateRequest(pilot_key="p100-role-scope-pilot"),
        actor=p89_seeded["admin"],
    )["pilot"]

    for slug in ("animal-x", "rawr-nation"):
        for index, content in enumerate(ready["contents"][slug]):
            service.add_item(
                pilot_id=pilot["id"],
                request=PilotItemRequest(
                    portfolio_content_id=content["id"],
                    content_version=int(content["version"]),
                    production_mode=(
                        ProductionMode.LOCAL_ONLY
                        if index == 0
                        else ProductionMode.MANAGED_RENDER
                    ),
                    live_delivery_evidence_required=(slug == "rawr-nation" and index == 1),
                ),
                actor=p89_seeded["admin"],
            )
    service.start(pilot_id=pilot["id"], actor=p89_seeded["admin"])

    with pytest.raises(psycopg.Error, match="assignment to every pilot brand"):
        service.signoff(
            pilot_id=pilot["id"],
            request=SignoffRequest(
                role=SignoffRole.REVIEWER,
                decision=SignoffDecision.APPROVED,
                rationale="This Reviewer holds the role but is outside both pilot brand assignments.",
            ),
            actor=p89_seeded["reviewer"],
        )
