from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p9-step-02.md")


def test_p9_restore_rehearsal_references_p8_backup_and_dry_run() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p8-step-03.md",
        "docs/operations/p9-step-01.md",
        "selecting a backup candidate",
        "verifying backup metadata and checksum",
        "isolated target",
    ]:
        assert term in content


def test_p9_restore_rehearsal_documents_isolation_and_preparation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "separate from production database",
        "network-restricted",
        "accessible only to rehearsal operators",
        "disposable after evidence is captured",
        "Confirm target environment is isolated.",
        "Confirm backup checksum.",
        "Confirm no production traffic points to the restore target.",
        "Confirm restore target can be destroyed after rehearsal.",
    ]:
        assert term in content


def test_p9_restore_rehearsal_documents_execution_and_runtime_checks() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "pg_restore --clean --if-exists --no-owner --no-acl --dbname \"$DATABASE_URL\" backup.dump",
        "Inject restore target `DATABASE_URL` outside git.",
        "Run database health check.",
        "Run migration status check.",
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/config",
        "protected routes require operator access",
    ]:
        assert term in content


def test_p9_restore_rehearsal_documents_verification_stop_conditions_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "backup checksum is recorded",
        "queue route can read expected restored data",
        "audit route can read expected restored data",
        "restore target is not isolated",
        "backup checksum is missing or mismatched",
        "restored target receives live production traffic",
        "restore target name",
        "backup file name",
        "destroy or retention decision",
        "Do not record passwords, tokens, connection strings, or private runtime values.",
    ]:
        assert term in content


def test_p9_restore_rehearsal_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No restore over live production traffic.",
        "No shared production restore target.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No public production launch.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
    ]:
        assert term in content
