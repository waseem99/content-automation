Feature: Phase 1 platform foundation
  Workflow foundation must be deterministic, auditable, and executable in CI.

  Scenario: Migrations apply cleanly in a disposable PostgreSQL database
    Given a clean PostgreSQL database
    When CI applies all numbered migrations
    Then every migration is applied in order and database health is reported

  Scenario: Previously deployed migrations cannot be silently edited
    Given a migration has already been applied
    When the SQL file is changed after deployment
    Then the migration checker fails with a checksum mismatch

  Scenario: Workflow events are append-only and state changes use the state service
    Given a workflow run and stage execution exist
    When workers, gates, or operators change status
    Then changes are recorded through guarded state transitions and append-only events

  Scenario: Worker execution is idempotent under duplicate requests
    Given two duplicate worker requests use the same idempotency fields
    When they are submitted concurrently
    Then only one execution is billable and duplicate callers reuse or observe the existing run

  Scenario: Human review requires identity, rationale, checklist, and no self-approval
    Given a gate requires operator review
    When a reviewer records a decision
    Then identity, rationale, checklist evidence, and self-review prevention are enforced

  Scenario: Budget limits and unknown pricing stop provider work before spend
    Given a provider call would exceed policy or uses unknown pricing
    When a worker is dispatched
    Then the budget guard prevents execution and records a stop or review event

  Scenario: Test fixtures have recorded safe provenance
    Given golden media fixtures are committed for acceptance tests
    When CI validates fixture provenance
    Then every fixture has a safe source type, license status, purpose, and content hash

  Scenario: CI scans for committed sensitive values and dependency conflicts
    Given a pull request changes source, workflow, documentation, or fixture files
    When CI runs acceptance checks
    Then sensitive value patterns and dependency conflicts are detected before merge
