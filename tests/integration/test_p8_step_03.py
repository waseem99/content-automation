from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p8-step-03.md")


def test_p8_backup_runbook_documents_triggers_and_preparation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Backup triggers",
        "production deployment",
        "database migration",
        "rollback rehearsal",
        "restore rehearsal",
        "Confirm the target environment.",
        "Confirm migrations are applied.",
        "GET /runtime/ready",
        "backup destination is encrypted",
    ]:
        assert term in content


def test_p8_backup_runbook_documents_backup_command_and_storage() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "pg_dump --format=custom --no-owner --no-acl --file backup.dump \"$DATABASE_URL\"",
        "content-automation-operator-ENVIRONMENT-YYYYMMDD-HHMMSS.dump",
        "encrypted at rest",
        "access controlled",
        "stored outside the running application container",
        "checksum",
    ]:
        assert term in content


def test_p8_restore_runbook_documents_restore_steps_and_verification() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Restore preparation",
        "Confirm restore target environment.",
        "Confirm backup checksum.",
        "Confirm rollback window and decision owner.",
        "pg_restore --clean --if-exists --no-owner --no-acl --dbname \"$DATABASE_URL\" backup.dump",
        "Run database health check.",
        "Run migration status check.",
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "protected routes still require operator access",
        "audit and queue routes can read expected restored data",
    ]:
        assert term in content


def test_p8_backup_restore_runbook_documents_rehearsal_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Rehearsal cadence",
        "before first production deployment",
        "after migration changes",
        "No restore without confirming target environment.",
        "No restore without a fresh current-state backup.",
        "No production restore rehearsal against live production traffic.",
        "No backup stored inside the application container.",
        "No secret values in logs.",
        "No private runtime values in backup notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
    ]:
        assert term in content
