from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOUNDATION = ROOT / "migrations/0065_shared_artifact_storage_foundation.sql"
INTEGRITY = ROOT / "migrations/0066_shared_artifact_storage_integrity.sql"
PROVIDERS = ROOT / "src/application/shared_storage/providers.py"
RUNTIME = ROOT / "src/application/shared_storage/runtime.py"
SERVICE = ROOT / "src/application/shared_storage/service.py"
API = ROOT / "src/operator_api/shared_storage_runtime.py"


def test_database_stores_locators_checksums_and_token_digests_not_media_or_tokens() -> None:
    source = FOUNDATION.read_text(encoding="utf-8").lower()
    assert "storage_uri text" in source
    assert "sha256 char(64)" in source
    assert "token_digest char(64)" in source
    assert "bytea" not in source
    assert " raw_token" not in source
    assert "access_token text" not in source
    assert "credential_secret_ref" in source


def test_backend_abstraction_supports_local_and_s3_compatible_storage() -> None:
    providers = PROVIDERS.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "class SharedStorageProvider(Protocol)" in providers
    assert "class LocalSharedStorageProvider" in providers
    assert "class S3CompatibleSharedStorageProvider" in providers
    assert "VerifiedS3CompatibleSharedStorageProvider" in runtime
    assert "credential_secret_ref" in runtime
    assert "boto3.client" in runtime


def test_retention_legal_hold_and_restore_evidence_are_fail_closed() -> None:
    source = INTEGRITY.read_text(encoding="utf-8")
    assert "Legal hold blocks artifact deletion" in source
    assert "Retention period blocks artifact deletion" in source
    assert "Shared access, restore, and storage event evidence is append-only" in source
    assert "Backup snapshot manifest is immutable" in source


def test_signed_access_uses_digest_only_and_anonymous_media_endpoint() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    assert "secrets.token_urlsafe" in service
    assert "token_digest(token)" in service
    assert "hmac.compare_digest" in service
    assert '@app.get("/shared-media/{grant_id}"' in api
    media_route = api.split('@app.get("/shared-media/{grant_id}"', 1)[1]
    assert "Depends(authenticate)" not in media_route.split("def raise_shared_error", 1)[0]
    assert "FileResponse" in media_route
    assert "RedirectResponse" in media_route


def test_no_provider_credentials_or_publication_controls_are_added() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROVIDERS, RUNTIME, SERVICE, API)
    ).lower()
    assert "aws_secret_access_key" not in combined
    assert "access_key_id" not in combined
    assert "publish" not in combined
    assert "youtube" not in combined
    assert "facebook" not in combined
