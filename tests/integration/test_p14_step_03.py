from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p14-step-03.md")


def test_p14_access_certification_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-02.md",
        "docs/operations/p13-readiness-report.md",
    ]:
        assert term in content


def test_p14_access_certification_documents_inventory_requirements() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "repository access",
        "deployment environment access",
        "database access",
        "object storage access",
        "dashboard access",
        "alert routing access",
        "evidence archive access",
        "operator tooling access",
        "emergency access",
        "service account access",
        "access surface",
        "account or role name",
        "access type",
        "business justification",
        "access owner",
        "approval status",
        "last activity signal",
        "removal action owner",
    ]:
        assert term in content


def test_p14_access_certification_documents_roles_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "access certification owner",
        "access surface owner",
        "reviewer",
        "evidence owner",
        "removal action owner",
        "exception owner",
        "audit package owner",
        "primary owner and backup owner",
        "Access rows without owners cannot be certified.",
        "access certification quarterly",
        "emergency access review monthly",
        "service account review quarterly",
        "privileged access review monthly",
        "access review after any material production change",
        "access evidence review before audit package closeout",
    ]:
        assert term in content


def test_p14_access_certification_documents_decisions_and_closure() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "access approved with current evidence",
        "access removal required",
        "access owner update required",
        "justification refresh required",
        "evidence refresh required",
        "exception accepted with owner and expiry date",
        "blocked because inventory is incomplete",
        "inventory is complete",
        "every access row has an owner",
        "every access row has a reviewer",
        "every approval decision has evidence",
        "removal actions have owners and target review dates",
        "evidence archive entry is recorded",
        "next review date is recorded",
    ]:
        assert term in content


def test_p14_access_certification_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "access inventory is missing",
        "business justification is missing",
        "approval status is missing",
        "evidence source is missing",
        "removal action lacks owner",
        "accepted exception lacks expiry date",
        "evidence contains secret values",
        "notes contain private runtime values",
        "workflow gate bypass is requested",
        "No access review closure with missing inventory.",
        "No access certification closure without evidence.",
        "No ownerless production access row.",
        "No approval without reviewer.",
        "No accepted exception without owner and expiry date.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
