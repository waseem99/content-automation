# Ops Storage and Observability

Issue #12 adds the first production infrastructure layer for storage, configuration checks, structured events, readiness, upload validation and metrics.

## Storage

- `LocalStorageProvider` is the local-development adapter.
- Storage is separated by purpose: assets, rights evidence, outputs and temporary files.
- Rights evidence maps to restricted access.
- Development signed URLs are time-bound and include access level plus expiry.
- Paths are resolved under the configured root and traversal is rejected.

## Temporary files

`TemporaryFileManager` only scans the temporary namespace. Permanent assets, evidence and outputs are not deleted by cleanup.

## Configuration checks

- `SecretProvider` defines the configuration provider interface.
- `EnvSecretProvider` is allowed for local development.
- Production validation fails when required configuration is expected from env only.
- Reports return names and status only, not raw values.

## Observability

- Structured events carry workflow, stage, worker, asset and provider correlation fields.
- Redaction masks sensitive keys and configured value patterns.
- In-process metrics support counters and totals for workflow, stage, provider and review tracking.

## Health and readiness

Readiness can check database health, storage availability and required configuration presence. Readiness fails if required dependencies are unavailable.

## Upload validation

`MediaUploadValidator` validates extension, MIME type, size and optional probe checks before media is accepted into storage.
