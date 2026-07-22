# P99 Operations Runbooks

These procedures are environment-neutral. Examples target an isolated staging environment. Do not paste credentials into commands, tickets, logs, or this repository. Resolve credential references through the approved secret manager at runtime.

## 1. Recreate staging

1. Copy `config/staging.env.example` outside the repository and replace only environment-specific values.
2. Record the intended Git SHA, image digest, configuration digest, and migration head.
3. Validate the compose model without starting services:
   `docker compose --env-file <external-env-file> -f compose.staging.yml config`
4. Build the pinned source revision locally or in CI:
   `docker compose --env-file <external-env-file> -f compose.staging.yml build --pull`
5. Start PostgreSQL and the one-shot migration container:
   `docker compose --env-file <external-env-file> -f compose.staging.yml up -d postgres`
   `docker compose --env-file <external-env-file> -f compose.staging.yml run --rm migrate`
6. Start the API and wait for `/runtime/ready` to report success:
   `docker compose --env-file <external-env-file> -f compose.staging.yml up -d api`
7. Record the release through `/operations/releases`, transition it through `deploying` to `healthy`, and retain the readiness response as evidence.
8. Run the focused smoke checks. Do not enable live renderer, analytics-provider, or publishing credentials during recreation drills.

Rollback: stop the API, select the immediately previous healthy release, rebuild that exact Git SHA/image digest, run migration compatibility checks, start it, verify readiness, and mark the failed release `rolled_back` with `previous_release_id` preserved.

## 2. API outage

Trigger: readiness is unhealthy, repeated safe `500` responses, database connectivity loss, or the `api_unhealthy` alert.

1. Pause delivery workers and scheduled publication claims. Do not delete queued work.
2. Capture the request ID, release key, Git SHA, image digest, and readiness checks. Never capture raw authorization headers or request bodies.
3. Check PostgreSQL reachability and migration status with the repository database CLI.
4. If the current release caused the outage, execute the release rollback procedure.
5. If the database is unavailable, keep workers stopped and follow the database restore runbook only in an isolated recovery environment.
6. Resolve the alert only after readiness remains healthy through the agreed observation window.

## 3. Failed renderer or generation worker

Trigger: repeated retryable renderer errors, dead-letter jobs, expired leases, or the `worker_failed` alert.

1. Disable or mark the affected renderer catalogue entry unavailable; do not alter immutable historical versions.
2. Allow valid running leases to expire or cancel them explicitly. Never reuse a lease token.
3. Run stale recovery. Confirm the timed-out attempt remains retained and the job returns to `queued` only when attempts remain.
4. Claim with a healthy worker or approved fallback provider.
5. Verify one and only one successful output and retained attempt history.
6. Record a `worker_restart` or renderer-failure drill with job, attempt, worker, and output evidence.

## 4. Delayed or stalled queue

Trigger: ready jobs exceed the stall threshold, leases expire, or the `queue_stalled` alert.

1. Inspect queue depth by job type, provider, brand, age, and dependency state.
2. Confirm workers are healthy and have permission for the affected job types/brands.
3. Recover expired leases; do not manually update job status or delete attempts.
4. Check blocked dependencies and unavailable renderer/storage prerequisites.
5. Scale only the constrained worker pool and preserve idempotency keys.
6. Resolve the alert after queue age and expired leases return below threshold.

## 5. Storage issue or low capacity

Trigger: missing/quarantined objects, checksum mismatch, backup failure, or the `storage_low` alert.

1. Stop jobs that would read or write the affected backend.
2. Mark the backend unavailable; do not mutate object checksums or storage evidence.
3. Compare canonical SHA-256, object size, version, and artifact-role metadata.
4. Restore one object into an isolated path using `python -m src.operations.cli artifact-restore-drill` with the recorded archive checksum.
5. Verify the restored manifest and checksum before registering restore evidence.
6. Increase capacity through a versioned quota policy if required; never bypass the quota trigger.

## 6. Database backup and restore drill

1. Create a custom-format schema backup:
   `python -m src.operations.cli database-backup --destination <isolated-path>/football_brief.dump --environment staging`
2. Record the SHA-256 and size in `/operations/backups` together with the artifact archive evidence.
3. Restore only into an isolated staging/recovery database:
   `python -m src.operations.cli database-restore-drill --backup <path> --expected-sha256 <sha256> --expected-migration-head <filename> --environment staging --allow-destructive-drill`
4. Verify migration head, representative row counts, one approved release, one delivery reference, and one analytics observation.
5. Record `/operations/restores` and complete the `database_restore` drill.

Direct production restoration is deliberately disabled by the utility. Production recovery must restore into an isolated database, verify it, then follow the approved cutover procedure.

## 7. Publication pause

Trigger: legal/compliance instruction, platform incident, incorrect release, API outage, or unresolved critical alert.

1. Stop publisher workers and scheduled claim loops.
2. Cancel only queued or scheduled delivery requests with a recorded reason. Do not delete delivery requests, attempts, or platform references.
3. Reconcile already submitted platform references and record observed status.
4. Leave final releases and manifests immutable. Create a child release for any correction.
5. Resume only after Reviewer approval, Publisher confirmation, and critical-alert resolution.

## 8. Alert handling

- `open` → `acknowledged` when an Admin accepts ownership.
- `open` or `acknowledged` → `resolved` only after the measured condition clears.
- Repeated identical observations reuse the same immutable alert evidence rather than rewriting it.
- New evidence produces a new append-only alert event.

## 9. Security incident

1. Disable affected credential references in the secret manager; never commit replacements.
2. Pause publication and paid-provider execution.
3. Preserve request IDs, job IDs, attempt IDs, release identity, and hashed remote/user-agent evidence.
4. Rotate credentials outside Git and restart only the affected service.
5. Run dependency, repository, and container scans before resuming.
6. Record the incident as a drill/evidence entry without secret material.

## 10. Evidence required to close an incident or drill

- environment and exact release identity;
- start/end timestamps and operator;
- alert, release, backup, restore, job, attempt, and platform-reference IDs as applicable;
- checksums and migration head;
- readiness and monitoring results;
- confirmation that no job/output was lost or duplicated;
- rationale and follow-up actions.
