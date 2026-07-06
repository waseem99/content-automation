# Foundation Closeout Checklist

Use this checklist before starting Phase 2 content-intelligence or editorial agents.

## Phase 0 publish-safety controls

- [x] Canonical asset registry exists for source, generated, derivative, evidence, voice, music, font, render and output files.
- [x] Rights evidence is represented as canonical assets.
- [x] Rights approvals require compatible platform, territory, use, evidence, attribution and validity windows.
- [x] Rights gate records aggregate and per-asset audit decisions.
- [x] Extracted source footage is blocked unless explicitly approved.
- [x] Preview and publish manifest modes are distinct.
- [x] Preview outputs remain non-publishable.
- [x] Publish manifests are immutable and hash-addressed.
- [x] Approved voice policy blocks unapproved provider voices and missing consent evidence.
- [x] Music and font policy coverage is represented in the publish-safety matrix.
- [x] Provider-generation lineage links provider call, parent asset, output asset, hashes and workflow stage.
- [x] Publish quality reports gate publication packages.
- [x] Blocking quality reports and human-review reports prevent release package creation.

## Phase 1 operating foundation

- [x] PostgreSQL migration runner is forward-only and checksum-aware.
- [x] Workflow runs persist version, input hash, state, operator context and timestamps.
- [x] Stage executions persist attempts, status, input/output hashes, worker/tool identifiers and operator context.
- [x] Workflow events are append-only.
- [x] State changes go through guarded transition services.
- [x] Retry and resume preserve prior attempts.
- [x] Upstream output changes invalidate dependent stages.
- [x] Worker idempotency keys prevent duplicate successful work.
- [x] Duplicate/concurrent worker requests do not duplicate charged provider rows.
- [x] Human review requests capture target, assignment, rationale, checklist and self-approval prevention.
- [x] Budget checks run before provider work.
- [x] Provider calls and cost entries reconcile to workflow totals.
- [x] Publish media resolves through registered asset IDs and controlled storage.
- [x] Storage, configuration validation, structured logs, redaction, metrics and readiness checks exist.
- [x] CI applies migrations to disposable PostgreSQL and runs acceptance/regression suites.

## Closeout PR requirements

- [x] Readiness report committed.
- [x] Closeout checklist committed.
- [x] Negative pilot test committed.
- [x] Traceability/readiness test committed.
- [x] Closeout workflow committed.
- [ ] Closeout workflow green on exact PR head.
- [ ] P1 Acceptance Harness green on exact PR head.
- [ ] PR merged into `test` using validated head SHA.
- [ ] Epic #14 updated and closed as completed.
- [ ] Epic #15 updated and closed as completed.

## Phase 2 entry rule

Do not create or merge content-intelligence, research, script, scoring, trend, or publishing agents until both #14 and #15 are closed as completed.
