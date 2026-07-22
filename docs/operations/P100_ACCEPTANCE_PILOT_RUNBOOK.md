# P100 Acceptance Pilot Runbook

## Purpose

Use this runbook to validate the complete content operating model with a small, controlled pilot before broader use. It is written for an operations lead, producer, reviewer, or publisher who does not need to change code.

This runbook does **not** deploy Vercel, publish content, start a managed renderer, create a Git tag, or handle platform credentials. The system records evidence and decisions. Any approved live delivery is performed separately under the organisation's existing controlled publishing process, then its result is recorded here without storing credentials.

## Pilot outcome

A successful pilot contains exactly four content items:

- two for **Animal X**;
- two for **Rawr Nation**;
- one local-only item and one managed-render item for each brand;
- one preserved revision cycle for script, narration, and visuals;
- a successful simulated staging delivery for every item;
- one separately approved live-delivery result recorded after all sign-offs;
- complete evidence, no unresolved major or critical defects, and three independent approvals.

Only after all gates pass may an Admin accept the pilot and record the production release tag.

## Roles

- **Admin:** creates the pilot, adds items, starts or retires it, binds operations evidence, and performs final acceptance.
- **Producer:** prepares content through the normal production workflow. A Producer cannot accept the pilot.
- **Reviewer:** collects and reviews evidence, opens defects, and records the Reviewer sign-off.
- **Publisher:** records the Publisher sign-off and, after separate human approval, records the external live-delivery result.

The Admin, Reviewer, and Publisher sign-offs must be made by three different active users. Each non-Admin user must be assigned to both pilot brands.

## Before starting

Confirm all of the following:

1. P99 staging readiness is healthy and the database migration head includes P100 migrations.
2. Animal X and Rawr Nation are active brands with current brand and narration presets.
3. Active Admin, Producer, Reviewer, and Publisher identities exist with correct brand assignments.
4. The four candidate content records are current and have not already been used in this pilot version.
5. Managed-render candidates already have an approved routing plan and spend approval. Do not run managed work before approval.
6. The backup/restore drill, worker restart drill, and this runbook validation can be recorded as evidence.
7. No production or platform credential is pasted into pilot notes, evidence, defects, or screenshots.

Stop immediately if any prerequisite is missing.

## Step 1 — Create the pilot

An Admin creates one pilot using a stable key such as `p100-production-acceptance`.

The system fixes the scope to:

- brands: `animal-x` and `rawr-nation`;
- two items per brand;
- four items total;
- required modes: `local_only` and `managed_render`;
- simulated staging delivery for every item;
- external live-result evidence only after sign-off.

If an editable pilot with the same key already exists, the system returns that pilot instead of creating a duplicate.

## Step 2 — Add exactly four items

Add the current version of each content item:

| Brand | Item 1 | Item 2 |
|---|---|---|
| Animal X | Local only | Managed render |
| Rawr Nation | Local only | Managed render |

For one item, mark that a separately approved live-delivery result will be required. The system rejects a fifth item, a third item for either brand, an unsupported brand, or an old content version.

## Step 3 — Start the pilot

The Admin starts the pilot only after all four items are present. After start, item identity, brand, content version, production mode, and required revision stages are immutable.

## Step 4 — Complete production and one revision cycle

For every item, complete the normal approved workflow:

1. approved concept and source evidence;
2. approved script;
3. a new script version linked to its parent with a revision reason;
4. approved narration and mix QC;
5. a new narration mix version linked to its parent;
6. approved visual project and selected shots;
7. a new visual shot version linked to its parent with a revision reason;
8. approved routing explanation and spend decision;
9. renderer/model and artifact lineage;
10. final QA, playback review, and approved release manifest.

Old versions must remain available. Regenerate only the affected stage. Do not overwrite or delete prior evidence.

## Step 5 — Complete simulated staging delivery

Every item must have a successful delivery request where:

- environment is `staging`;
- delivery is explicitly simulated;
- the exact approved final release and content version are used;
- the result status is successful.

A simulated result is evidence only. It does not publish externally.

## Step 6 — Collect item evidence

An Admin or assigned Reviewer collects evidence for each item. The collector reads canonical records and records both passing and failing results. Operators cannot submit a free-form `passed=true` value.

Each item requires passed evidence for:

- brand profile and narration preset;
- role assignments;
- concept, sources, and script approval;
- script, narration, and visual revisions;
- narration and visual approval;
- routing explanation and spend approval;
- renderer and artifact lineage;
- final QA and release manifest;
- Publisher decision;
- simulated staging delivery;
- analytics observation and production economics.

An item remains blocked until every required category passes.

## Step 7 — Record operations evidence

An Admin binds verified evidence for:

- a successful database and artifact backup/restore drill;
- a successful worker restart/resume drill;
- validation that this runbook was followed by a non-developer operator.

For the runbook evidence, use the normal Admin operations-drill controls:

1. Start a drill with environment `staging` and drill kind `runbook_validation`. Do not attach a release or backup record.
2. Have a non-developer operator follow this runbook and complete the checklist and stop-condition review.
3. Complete the drill with status `passed` and an evidence object containing exactly these required values:
   - `runbook_path`: `docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md`;
   - `runbook_sha256`: the lowercase SHA-256 of this packaged file;
   - `operator_profile`: `non_developer`;
   - `checklist_completed`: `true`.
4. Include a brief non-secret validation note. The operations service adds the completing Admin and completion time.
5. Bind the resulting canonical drill ID to the pilot as category `runbook_validation` and subject type `operations_drill_run`.

The system rejects production-environment runbook drills, attached release or backup IDs, incomplete evidence, a stale runbook digest, and unrelated staging or security drills. Use canonical P99/P100 evidence identifiers only. Do not enter arbitrary labels or secret values.

## Step 8 — Manage defects

A Reviewer or Admin records each defect with severity and evidence.

- **Critical:** always blocks rollout.
- **Major:** always blocks rollout.
- **Minor:** must be resolved or deliberately waived with a written reason.

Evidence and sign-offs are append-only. If a sign-off is rejected or the pilot cannot be corrected without changing immutable scope, an Admin retires the pilot with a reason and creates the next traced child version. Do not edit or delete the failed history.

## Step 9 — Record independent sign-offs

After all four items and operations evidence pass, record:

1. Admin approval;
2. Reviewer approval;
3. Publisher approval.

Each sign-off stores an immutable evidence snapshot and digest. A rejected sign-off blocks acceptance and should lead to defect handling or a retired child revision.

## Step 10 — Record one controlled live result

Only after the three sign-offs, obtain explicit human approval through the organisation's existing publishing process. The P100 system provides no live-delivery execution endpoint.

A Publisher records only:

- the exact pilot item and approved final release;
- platform name;
- non-secret platform reference;
- result status;
- SHA-256 of the external response evidence;
- a small evidence object with no credential or token.

At least one required item must have a `submitted` or `published` result. A failed or removed result does not satisfy acceptance.

## Step 11 — Accept and define the release tag

Before acceptance, calculate the SHA-256 of this exact file:

`docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md`

The Admin submits:

- a production release tag beginning with `prod-`, for example `prod-p100-2026.07.22-01`;
- the lowercase 64-character runbook SHA-256.

The application verifies the supplied digest against the packaged runbook. In one database transaction, it then verifies every existing gate and, only if all pass:

- changes the pilot to `accepted`;
- records the immutable production release tag;
- records the accepting/tagging Admin and timestamp;
- records the exact runbook path and digest.

The system does not automatically create a Git tag, deploy an environment, or publish content. Release management may use the recorded label after human review.

## Stop conditions

Do not accept the pilot when any of these are true:

- fewer or more than four items;
- wrong brand or production-mode coverage;
- missing or failed evidence;
- managed rendering without spend approval;
- release without final package approval;
- missing simulated staging result;
- missing restore, restart, or runbook evidence;
- open major or critical defect;
- missing, rejected, duplicate-user, or wrong-role sign-off;
- missing required live-result evidence;
- runbook digest mismatch;
- release tag already used;
- any request to bypass role or brand scope.

## Recovery

- **Wrong item or scope:** retire the pilot and create a child version.
- **Failed evidence:** correct the source workflow, preserve the old version, then recollect.
- **Rejected sign-off:** open or update defects, retire when necessary, and create a child version.
- **Runbook digest mismatch:** use the packaged file, recalculate its SHA-256, and retry. Do not disable verification.
- **Duplicate release tag:** choose a new approved label. Never rewrite an accepted pilot.
- **Staging unhealthy:** follow the P99 staging, outage, queue, storage, or backup runbook before continuing.

## Completion record

A completed pilot record should show:

- status `accepted`;
- four passed items across both brands and both modes;
- complete immutable evidence and revision lineage;
- zero open major or critical defects;
- three distinct approved role sign-offs;
- at least one qualifying recorded live result;
- production release tag;
- exact runbook path and SHA-256;
- accepting Admin and timestamp.
