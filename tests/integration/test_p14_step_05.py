from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p14-step-05.md")


def test_p14_audit_package_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-02.md",
        "docs/operations/p14-step-03.md",
        "docs/operations/p14-step-04.md",
        "docs/operations/p13-readiness-report.md",
    ]:
        assert term in content


def test_p14_audit_package_documents_contents_and_mapping() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "package summary",
        "production governance evidence index",
        "compliance evidence map reference",
        "security review cadence reference",
        "access certification reference",
        "control testing reference",
        "operational runbook reference",
        "incident and action tracking reference",
        "resilience evidence reference",
        "CI validation evidence reference",
        "exception register reference",
        "closeout readiness checklist",
        "governance section to release and lifecycle governance evidence",
        "security section to security review records",
        "access section to access certification records",
        "controls section to control testing records",
        "validation section to PR references and CI run identifiers",
    ]:
        assert term in content


def test_p14_audit_package_documents_fields_and_review_flow() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "package section",
        "evidence source",
        "evidence owner",
        "package owner",
        "reviewer",
        "evidence status",
        "linked PR or issue reference",
        "linked CI run identifier when applicable",
        "package readiness status",
        "confirm package scope",
        "confirm evidence map is current",
        "confirm access certification evidence is complete",
        "confirm security review evidence is current",
        "confirm control testing evidence is complete",
        "confirm open actions have owners",
        "confirm accepted exceptions have expiry dates",
        "confirm excluded evidence is documented",
        "record final reviewer decision",
    ]:
        assert term in content


def test_p14_audit_package_documents_exclusions_and_readiness() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "private environment dumps",
        "external package exports",
        "screenshots that reveal restricted runtime values",
        "Use references, identifiers, and archive entry names instead of sensitive evidence content.",
        "every package section has an evidence source",
        "every evidence source has an owner",
        "every package section has a reviewer",
        "open actions have action owners",
        "accepted exceptions have owners and expiry dates",
        "excluded evidence is listed",
        "final reviewer decision is recorded",
    ]:
        assert term in content


def test_p14_audit_package_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "package scope is missing",
        "evidence map is not current",
        "access certification evidence is incomplete",
        "security review evidence is missing",
        "control testing evidence is incomplete",
        "open action lacks owner",
        "accepted exception lacks expiry date",
        "evidence exclusion is not documented",
        "package contains secret values",
        "package contains private runtime values",
        "external export is requested",
        "workflow gate bypass is requested",
        "No audit package readiness without complete evidence references.",
        "No package section without owner and reviewer.",
        "No accepted exception without owner and expiry date.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No external export.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
    ]:
        assert term in content
