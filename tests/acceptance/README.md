# Acceptance Test Strategy

The source-of-truth business scenarios are:

- `docs/acceptance/phase-0-risk-containment.feature`
- `docs/acceptance/phase-1-platform-foundation.feature`

## Current executable coverage

`test_migration_contracts.py` protects the initial SQL contracts without requiring a database. It verifies required tables, fail-closed defaults, idempotency fields, publish-manifest approval, quality outcomes, and non-negative cost controls.

## Required implementation coverage

As application services are introduced, each Gherkin scenario must be mapped to one of:

1. Unit test — deterministic policy or state logic.
2. PostgreSQL integration test — transaction, uniqueness, foreign key, or constraint behavior.
3. Service integration test — workflow/repository/storage interaction.
4. Media integration test — FFmpeg/render/QC behavior using rights-safe fixtures.
5. Manual evidence test — only where legal/editorial judgment cannot be automated; reviewer and evidence must be recorded.

## Test naming

Use stable scenario IDs in automated test docstrings or markers:

- `P0-RIGHTS-001` unapproved match footage
- `P0-RIGHTS-002` approved platform-specific rights
- `P0-RIGHTS-003` expired rights
- `P0-RIGHTS-004` unapproved search image
- `P0-RIGHTS-005` attribution required
- `P0-VOICE-001` cloned voice without consent
- `P0-VOICE-002` approved narrator
- `P0-AUDIO-001` unapproved music
- `P0-RENDER-001` placeholder blocked in publish mode
- `P0-RENDER-002` preview watermark and no publication package
- `P0-LINEAGE-001` preserve source and derivative
- `P0-MANIFEST-001` asset hash mismatch
- `P0-BRAND-001` hook begins at frame one
- `P1-WORKFLOW-001` start workflow
- `P1-WORKFLOW-002` duplicate workflow identity
- `P1-WORKER-001` provider idempotency
- `P1-WORKER-002` immutable retry history
- `P1-WORKFLOW-003` resume after failure
- `P1-WORKFLOW-004` stale-output invalidation
- `P1-REVIEW-001` required human gate
- `P1-REVIEW-002` rejection and revision history
- `P1-COST-001` budget circuit breaker
- `P1-COST-002` cost reconciliation
- `P1-STORAGE-001` asset-ID resolution
- `P1-SECURITY-001` secret redaction
- `P1-MANIFEST-001` immutable publish manifest
- `P1-MANIFEST-002` manifest mutation rejection
- `P1-AUDIT-001` append-only transitions
- `P1-AUDIT-002` complete audit report
- `P1-QC-001` quality report blocks packaging

## Required CI gates

- Critical compliance tests: 100% pass.
- Migration application: 100% pass on clean PostgreSQL.
- Secret scan: no unresolved high-confidence secret.
- Dependency scan: no unresolved critical vulnerability.
- Type checking and unit tests: pass.
- Media/golden tests: pass for affected rendering changes.

## Fixture policy

Test media must be one of:

- Created specifically for the test suite.
- Public domain with evidence recorded.
- Appropriately licensed with evidence recorded.
- Synthetic and non-infringing.

Do not commit broadcast match footage, commercial music, scraped player images, or unverified Creative Commons downloads as fixtures.
