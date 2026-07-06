from src.application.observability.health import HealthCheckService
from src.application.secrets.provider import EnvSecretProvider, RuntimeEnvironment, SecretRequirement, SecretValidator
from src.application.storage.provider import LocalStorageProvider
from src.application.storage.upload_validation import MediaUploadValidator, UploadValidationError, UploadValidationPolicy

import pytest


def test_upload_validator_accepts_allowed_file(tmp_path):
    file = tmp_path / "image.png"
    file.write_bytes(b"png")
    result = MediaUploadValidator().validate(file)
    assert result.extension == ".png"
    assert result.mime_type == "image/png"


def test_upload_validator_rejects_bad_extension(tmp_path):
    file = tmp_path / "bad.exe"
    file.write_bytes(b"bad")
    with pytest.raises(UploadValidationError):
        MediaUploadValidator().validate(file)


def test_upload_validator_rejects_large_file(tmp_path):
    file = tmp_path / "image.png"
    file.write_bytes(b"too-large")
    policy = UploadValidationPolicy(max_size_bytes=2)
    with pytest.raises(UploadValidationError):
        MediaUploadValidator(policy).validate(file)


def test_readiness_fails_for_missing_secret(tmp_path):
    service = HealthCheckService(
        storage=LocalStorageProvider(tmp_path / "storage"),
        secrets=SecretValidator(EnvSecretProvider(), environment=RuntimeEnvironment.LOCAL),
    )
    report = service.readiness(requirements=(SecretRequirement(name="MISSING_DEMO_SECRET"),))
    assert report.ok is False
    assert report.secrets is not None
    assert report.secrets.missing == ("MISSING_DEMO_SECRET",)


def test_readiness_passes_for_storage_only(tmp_path):
    report = HealthCheckService(storage=LocalStorageProvider(tmp_path / "storage")).readiness()
    assert report.ok is True
