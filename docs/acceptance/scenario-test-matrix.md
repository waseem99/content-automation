# Phase 0/1 Acceptance Scenario-to-Test Matrix

This matrix is the CI traceability layer for Phase 0 risk controls and Phase 1 platform-foundation BDD scenarios. A scenario may map to more than one executable test because the platform uses layered static contracts, PostgreSQL integration tests, and compliance regressions.

| Feature | Scenario | Automation status | Executable evidence | Notes |
|---|---|---:|---|---|
| Phase 0 risk controls | Candidate assets cannot be used for publish output | automated | `tests/integration/test_rights_gate.py`<br>`tests/integration/test_quality_package_guard.py` | Package guards fail closed before publication. |
| Phase 0 risk controls | Expired license coverage fails publish validation | automated | `tests/integration/test_rights_gate.py`<br>`tests/integration/test_rights_gate_revalidation.py` | Platform, territory, campaign, use, expiry, and revalidation are covered. |
| Phase 0 risk controls | Preview render output is non-publishable | automated | `tests/integration/manifest_runtime_cases.py`<br>`tests/acceptance/test_manifest_migration_contracts.py` | Preview mode is non-publishable and rejected for package publication. |
| Phase 0 risk controls | Publish manifests require approval, evidence, and stable hashes | automated | `tests/integration/test_manifest_builder.py`<br>`tests/acceptance/test_manifest_migration_contracts.py` | Publish packages require review, evidence, and immutable hashes. |
| Phase 0 risk controls | Unapproved voices and missing consent fail validation | automated | `tests/integration/test_evidence_and_voice_registry.py`<br>`tests/acceptance/test_voice_media_policy_contracts.py` | Approved voice registry and consent evidence are required. |
| Phase 0 risk controls | Generated media requires provider lineage | automated | `tests/acceptance/test_provider_lineage_contracts.py` | Provider request, response, parent and output evidence contracts are enforced. |
| Phase 0 risk controls | Quality gate rejects placeholders and unsafe publish output | automated | `tests/integration/test_quality_package_guard.py`<br>`tests/integration/test_quality_media_and_disclosure.py`<br>`tests/acceptance/test_quality_gate_contracts.py` | Findings, disclosure, placeholder, and media policy checks are required. |
| Phase 1 platform foundation | Migrations apply cleanly in a disposable PostgreSQL database | automated | `.github/workflows/p1-acceptance-harness.yml`<br>`tests/acceptance/test_migration_contracts.py` | CI applies all migrations against PostgreSQL 16. |
| Phase 1 platform foundation | Previously deployed migrations cannot be silently edited | automated | `tests/acceptance/test_migration_lock.py`<br>`tests/integration/test_migration_checksum_guard.py` | Lock-file and applied-checksum tests catch edits. |
| Phase 1 platform foundation | Workflow events are append-only and state changes use the state service | automated | `tests/integration/test_flow_events.py`<br>`tests/acceptance/test_state_machine_contracts.py` | State-machine guards and append-only events are validated. |
| Phase 1 platform foundation | Worker execution is idempotent under duplicate requests | automated | `tests/integration/test_worker_execution.py`<br>`tests/integration/test_worker_race.py` | Duplicate and concurrent requests do not create duplicate charged rows. |
| Phase 1 platform foundation | Human review requires identity, rationale, checklist, and no self-approval | automated | `tests/integration/test_gate_contracts.py`<br>`tests/integration/test_gate_blocking_checks.py`<br>`tests/acceptance/test_human_gate_contracts.py` | Operator decisions require evidence and cannot self-approve. |
| Phase 1 platform foundation | Budget limits and unknown pricing stop provider work before spend | automated | `tests/integration/test_budget_dispatcher.py` | Budget stop/review paths run before handler execution. |
| Phase 1 platform foundation | Test fixtures have recorded safe provenance | automated | `tests/acceptance/test_fixture_provenance.py` | Golden fixtures must have safe source type, license status, purpose, and hash. |
| Phase 1 platform foundation | CI scans for committed sensitive values and dependency conflicts | automated | `tests/acceptance/test_sensitive_pattern_scan.py`<br>`.github/workflows/p1-acceptance-harness.yml` | Local pattern scan plus `pip check` run in CI. |

## Manual evidence policy

Manual evidence is allowed only for external provider-console screenshots, third-party platform policy reviews, or branch-protection settings that cannot be asserted inside this repository. Any manual row must include an owner, evidence location, and expiry date. No current Phase 0/1 scenario is manual-only.
