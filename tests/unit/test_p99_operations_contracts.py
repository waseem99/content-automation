from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from src.operations import (
    BackupRestoreError,
    BackupRestoreManager,
    BackupSetRequest,
    OperationsService,
    OperationsSettings,
    RestoreEvidenceRequest,
)
from src.operations.validated_service import ValidatedOperationsService
from src.operator_api.operations_middleware import OperationsSafetyMiddleware


ROOT = Path(__file__).resolve().parents[2]
STAGING_COMPOSE = ROOT / "compose.staging.yml"
STAGING_ENV = ROOT / "config/staging.env.example"
PRODUCTION_ENV = ROOT / "config/production.env.example"
DOCKERFILE = ROOT / "Dockerfile"
RUNTIME_FACTORY = ROOT / "src/operator_api/runtime_factory.py"


def valid_production_settings(**overrides) -> dict:
    payload = {
        "_env_file": None,
        "environment": "production",
        "release_key": "release-2026-07-22-001",
        "git_sha": "1" * 40,
        "image_digest": "sha256:" + "2" * 64,
        "configuration_digest": "3" * 64,
        "migration_head": "0082_production_operations_integrity.sql",
        "allow_destructive_restore_drill": False,
    }
    payload.update(overrides)
    return payload


def test_public_operations_service_is_validated() -> None:
    assert OperationsService is ValidatedOperationsService


def test_production_settings_fail_closed_and_never_allow_destructive_restore() -> None:
    with pytest.raises(ValidationError, match="non-placeholder"):
        OperationsSettings(_env_file=None, environment="production")
    with pytest.raises(ValidationError, match="cannot be enabled"):
        OperationsSettings(**valid_production_settings(allow_destructive_restore_drill=True))
    settings = OperationsSettings(**valid_production_settings())
    assert settings.environment == "production"
    assert settings.allow_destructive_restore_drill is False


def test_backup_models_reject_secret_material_and_incomplete_restore() -> None:
    credential_like = "to" + "ken=" + "not-allowed"
    with pytest.raises(ValidationError, match="secret material"):
        BackupSetRequest(
            environment="staging",
            backup_key="backup-contract-001",
            database_object_ref=credential_like,
            artifact_object_ref="object:artifacts/backup.zip",
            database_sha256="a" * 64,
            artifact_sha256="b" * 64,
            migration_head="0082_production_operations_integrity.sql",
            database_bytes=10,
            artifact_bytes=5,
            retention_until="2030-01-01T00:00:00+00:00",
        )
    with pytest.raises(ValidationError, match="every database"):
        RestoreEvidenceRequest(
            backup_set_id="00000000-0000-4000-8000-000000000001",
            environment="staging",
            database_restored=True,
            artifacts_restored=False,
            migration_head_verified=True,
            database_sha256_verified=True,
            artifact_sha256_verified=True,
            verification={"drill": True},
        )


def test_artifact_backup_restores_exact_manifest_and_rejects_tampering(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "clip.bin").write_bytes(b"controlled-media-bytes\n" * 20)
    (source / "nested").mkdir()
    (source / "nested/thumbnail.bin").write_bytes(b"thumbnail-bytes")
    archive = tmp_path / "artifacts.zip"
    manager = BackupRestoreManager(
        database_url="postgresql://unused",
        environment="staging",
    )
    backup, manifest = manager.create_artifact_backup(source, archive)
    destination = tmp_path / "restored"
    restored = manager.restore_artifact_backup(
        archive,
        destination,
        expected_sha256=backup.sha256,
        allow_destructive_drill=True,
    )
    assert restored["object_count"] == 2
    assert (destination / "clip.bin").read_bytes() == (source / "clip.bin").read_bytes()
    assert restored["manifest"] == manifest

    archive.write_bytes(archive.read_bytes() + b"tampered")
    with pytest.raises(BackupRestoreError, match="checksum mismatch"):
        manager.restore_artifact_backup(
            archive,
            tmp_path / "must-not-restore",
            expected_sha256=backup.sha256,
            allow_destructive_drill=True,
        )


def test_production_restore_is_disabled_even_with_explicit_flag(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "object.bin").write_bytes(b"one-object")
    archive = tmp_path / "artifacts.zip"
    staging = BackupRestoreManager(database_url="postgresql://unused", environment="staging")
    backup, _ = staging.create_artifact_backup(source, archive)
    production = BackupRestoreManager(database_url="postgresql://unused", environment="production")
    with pytest.raises(BackupRestoreError, match="direct production artifact restore is disabled"):
        production.restore_artifact_backup(
            archive,
            tmp_path / "production-restore",
            expected_sha256=backup.sha256,
            allow_destructive_drill=True,
        )


def test_request_middleware_enforces_ids_limits_and_safe_errors() -> None:
    settings = OperationsSettings(
        _env_file=None,
        max_request_body_bytes=1024,
        requests_per_minute=100,
    )
    app = FastAPI()
    app.add_middleware(OperationsSafetyMiddleware, settings=settings)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"size": len(body)}

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("private diagnostic must never reach the caller")

    client = TestClient(app, raise_server_exceptions=False)
    oversized = client.post("/echo", content=b"x" * 1025)
    assert oversized.status_code == 413
    assert oversized.json()["detail"] == "request_body_too_large"
    assert oversized.headers["x-request-id"] == oversized.json()["request_id"]

    failed = client.get("/explode", headers={"X-Request-ID": "req-custom-123"})
    assert failed.status_code == 500
    assert failed.json() == {
        "detail": "internal_server_error",
        "request_id": "req-custom-123",
    }
    assert "private diagnostic" not in failed.text


def test_per_instance_rate_limit_is_explicit_and_exempts_health() -> None:
    settings = OperationsSettings(_env_file=None, requests_per_minute=1)
    app = FastAPI()
    app.add_middleware(OperationsSafetyMiddleware, settings=settings)

    @app.get("/limited")
    def limited() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/limited").status_code == 200
    limited = client.get("/limited")
    assert limited.status_code == 429
    assert limited.json()["detail"] == "rate_limit_exceeded"
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200


def test_environment_templates_are_separate_read_only_and_deployment_neutral() -> None:
    staging = STAGING_ENV.read_text(encoding="utf-8")
    production = PRODUCTION_ENV.read_text(encoding="utf-8")
    compose = STAGING_COMPOSE.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    runtime = RUNTIME_FACTORY.read_text(encoding="utf-8")
    assert "OPS_ENVIRONMENT=staging" in staging
    assert "OPS_ENVIRONMENT=production" in production
    assert "OPS_ALLOW_DESTRUCTIVE_RESTORE_DRILL=false" in production
    assert "read_only: true" in compose
    assert "tmpfs:" in compose
    assert "USER app" in dockerfile
    assert "OperationsSafetyMiddleware" in runtime
    combined = "\n".join((staging, production, compose, runtime)).lower()
    assert "vercel" not in combined
    assert "generated-media" not in combined
    assert "youtube.googleapis.com" not in combined
