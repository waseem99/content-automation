from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p12-step-02.md")


def test_p12_access_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-01.md",
        "docs/operations/p11-step-05.md",
        "docs/operations/p11-step-04.md",
    ]:
        assert term in content


def test_p12_access_review_documents_cadence_inventory_and_roles() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Run once per quarter.",
        "Run after any major ownership change.",
        "repository access",
        "deployment access",
        "database access",
        "alert route access",
        "evidence archive access",
        "secret management access",
        "service account ownership",
        "access review owner",
        "security or guardrail reviewer",
    ]:
        assert term in content


def test_p12_access_review_documents_evidence_decisions_and_removals() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "access item ID",
        "business justification",
        "remove access",
        "reduce access",
        "create time-limited exception",
        "removal owner",
        "validation method",
        "completion evidence",
        "follow-up review date",
    ]:
        assert term in content


def test_p12_access_review_documents_exceptions_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "exception owner",
        "expiry date",
        "compensating control",
        "reviewer is also the sole access owner",
        "exception lacks expiry date",
        "emergency access lacks owner",
        "No access review closure with missing inventory.",
        "No permanent exception without expiry date.",
        "No reviewer-only approval for own access.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
    ]:
        assert term in content
