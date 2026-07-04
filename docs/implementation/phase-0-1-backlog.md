# Phase 0 and Phase 1 Implementation Backlog

Branch: `phase-0-1-foundation`  
Base branch: `test`

## Epics

- [EPIC P0 — Risk containment and publish safety](https://github.com/waseem99/content-automation/issues/14)
- [EPIC P1 — Workflow, audit, storage, and cost foundation](https://github.com/waseem99/content-automation/issues/15)

## Issue map

| Order | Issue | Outcome | Primary evidence |
|---:|---|---|---|
| 1 | [#7 PostgreSQL repositories](https://github.com/waseem99/content-automation/issues/7) | Database and transaction foundation | PostgreSQL migration/integration tests |
| 2 | [#1 Asset and rights registry](https://github.com/waseem99/content-automation/issues/1) | Canonical assets, hashes, rights, evidence | Phase 0 rights scenarios |
| 3 | [#8 Workflow state machine](https://github.com/waseem99/content-automation/issues/8) | State, events, retry/revision history | Phase 1 workflow scenarios |
| 4 | [#2 Rights gate](https://github.com/waseem99/content-automation/issues/2) | Fail-closed platform/territory/use checks | Negative rights tests |
| 5 | [#4 Voice, music, and font policy](https://github.com/waseem99/content-automation/issues/4) | Approved narrator and audio/font assets | Voice/music compliance tests |
| 6 | [#9 Worker contracts](https://github.com/waseem99/content-automation/issues/9) | Typed workers, idempotency, retries | Concurrency and invalidation tests |
| 7 | [#10 Human review service](https://github.com/waseem99/content-automation/issues/10) | Auditable gates and revision decisions | Approval/rejection workflow tests |
| 8 | [#5 Asset lineage](https://github.com/waseem99/content-automation/issues/5) | Source-to-derivative traceability | Lineage and synthetic-edit tests |
| 9 | [#11 Cost and budget control](https://github.com/waseem99/content-automation/issues/11) | Provider ledger and circuit breakers | Budget and reconciliation tests |
| 10 | [#12 Storage, secrets, observability](https://github.com/waseem99/content-automation/issues/12) | Safe media/secret operations | Redaction and storage tests |
| 11 | [#3 Preview/publish manifests](https://github.com/waseem99/content-automation/issues/3) | Immutable reproducible renders | Manifest/hash tests |
| 12 | [#6 Publish quality gate](https://github.com/waseem99/content-automation/issues/6) | Publication blocking and QC | Phase 0 regression suite |
| 13 | [#13 CI and acceptance harness](https://github.com/waseem99/content-automation/issues/13) | Continuous enforcement | CI reports and scenario matrix |

## Recommended delivery slices

### Slice A — Foundation and registration

Issues: #7, #1, #8

Demonstration:

1. Apply migrations to an empty PostgreSQL database.
2. Register one source image, one owned video, one music file, and one voice.
3. Start a workflow and inspect its append-only event stream.
4. Demonstrate transaction rollback after an intentional failure.

### Slice B — Fail-closed compliance

Issues: #2, #4, #5

Demonstration:

1. Show an extracted broadcast clip blocked as `internal_only`.
2. Show an expired image licence blocked.
3. Show an approved source image transformed into a traceable derivative.
4. Show an unauthorized cloned voice blocked.
5. Show an approved narrator and approved music passing.

### Slice C — Controlled execution

Issues: #9, #10, #11, #12

Demonstration:

1. Execute a reference worker twice with identical inputs and prove one provider charge.
2. Fail and retry a stage without overwriting attempt 1.
3. Stop a provider call before exceeding budget.
4. Require human approval before continuing.
5. Confirm representative API keys are redacted from logs and database records.

### Slice D — Reproducible rendering and release gate

Issues: #3, #6, #13

Demonstration:

1. Create a watermarked preview with one unresolved shot.
2. Prove the preview cannot be packaged for publication.
3. Create and approve an immutable publish manifest.
4. Render using only registered approved assets.
5. Show asset-byte modification causing a hash mismatch and block.
6. Show a passing quality report enabling packaging.
7. Run the full CI suite on a clean environment.

## Pull request rules

No implementation PR should close an issue unless it includes:

- Unit tests for business logic.
- PostgreSQL integration tests for repository/constraint behavior.
- Negative-path acceptance tests.
- Migration impact statement.
- Security and compliance impact statement.
- Provider cost impact statement where relevant.
- Rollback or forward-fix procedure.
- Evidence linking the implementation to the relevant BDD scenarios.

## Phase 0 release gate

Phase 0 is releasable only when:

- All issue #14 child tasks are complete.
- Every publish asset has an approved rights record and verified hash.
- No extracted match footage is publishable by default.
- No placeholder, unapproved voice, unapproved music/font, expired right, or hash mismatch can pass.
- All critical compliance tests pass at 100%.

## Phase 1 release gate

Phase 1 is releasable only when:

- All issue #15 child tasks are complete.
- A clean database can apply every migration.
- Workflow resume, retry, invalidation, and review behavior are demonstrated.
- Provider idempotency is proven under concurrency.
- Budget and cost reconciliation tests pass.
- Audit evidence can be exported for a complete test workflow.
- Secrets are absent from representative logs, exceptions, and persisted payloads.

## AI-agent freeze

Do not add content-intelligence, research, script, critic, or learning agents until:

1. Phase 0 publish gates are operational.
2. Phase 1 worker contracts and cost controls are operational.
3. Provider calls can be traced and deduplicated.
4. Human review can block and resume workflows.
5. CI enforces migrations and critical acceptance tests.
