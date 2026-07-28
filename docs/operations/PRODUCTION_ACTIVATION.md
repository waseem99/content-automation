# Content Automation production activation

This runbook is the canonical path for moving the existing Windows workstation from repository-ready to controlled real use.

## Product identity

- Product: Content Automation Platform
- Operator application: Creator Studio
- Repository: `waseem99/content-automation`
- Canonical branch: `test`
- Local application: `http://127.0.0.1:8000/app/dashboard`

The sales-acquisition/TalentTrack project is unrelated and must not be installed into this repository or runtime.

## Simplified role model

Creator Studio presents only three roles:

### Super Admin

- complete system and content access;
- team and role administration;
- brand and runtime configuration;
- production, review, release and delivery access;
- portfolio-wide access;
- the key is never shared with ordinary users.

### Admin

- complete day-to-day platform access;
- create and edit content;
- generate and revise scripts;
- start and retry production;
- review scripts, narration, visuals and releases;
- configure brands and users;
- create delivery requests;
- portfolio-wide access.

### Reviewer

- brand-scoped access;
- create and edit content;
- generate, submit, revise and review scripts;
- start and retry local production;
- select and review narration and visual candidates;
- approve or request changes;
- prepare and deliver approved releases;
- archive or supersede records through the audited workflow.

Hard deletion of approved evidence, artifacts, releases or audit history remains prohibited. Records are superseded, retired or archived so production evidence remains recoverable.

Internally, Reviewer retains the historical `producer` and `publisher` capability rows required by existing services. Those internal capabilities are not presented as separate roles.

## Existing workstation upgrade

From an elevated PowerShell in the repository root:

```powershell
git checkout test
git pull origin test

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\deploy_remote_content_automation.ps1 `
  -AcceptComfyModelLicense
```

The launcher:

- preserves PostgreSQL, models, artifacts, queued jobs and historical reviews;
- applies every migration, including the simplified-role migration;
- preserves the original local Admin secret by promoting it to Super Admin;
- creates separate Admin and Reviewer secrets;
- deactivates the old local Producer and Publisher identities;
- starts the always-on API and workers;
- exposes only the authenticated Creator Studio/API port through ngrok;
- records the HTTPS URL in `.runtime/remote-access.json`.

Keys are stored outside Git in `.runtime/operator-keys.json`.

## Remote-access boundary

Before deployment, configure ngrok locally:

```powershell
ngrok config add-authtoken <your-ngrok-token>
```

Only the HTTPS Creator Studio URL is shared. Never expose:

- PostgreSQL;
- Ollama;
- ComfyUI;
- worker processes;
- `.runtime/artifacts`;
- `.runtime/operator-keys.json`;
- the Super Admin key.

Run the readiness report after deployment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\check_production_readiness.ps1 `
  -RequireRemoteAccess
```

## First real browser workflow

Use one disposable internal content item first:

1. Sign in as Reviewer.
2. Create a content item from a manual brief.
3. Generate a local script.
4. Submit and review the exact script version.
5. Preserve one requested-change revision.
6. Approve the corrected script.
7. Start local narration and visual production.
8. Select narration takes and create the final mix.
9. Preserve one narration revision.
10. Select visual candidates and preserve one visual revision.
11. Approve narration and visuals.
12. Generate and play the complete MP4 preview.
13. Complete technical QA and release approval.
14. Restart the workstation service and confirm all data and artifacts persist.
15. Create and verify a backup before using client content.

## Official Higgsfield account setup

The repository supports only an official, account-authenticated Higgsfield route. Do not use browser cookies, private endpoints or desktop macro automation.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_higgsfield_official.ps1 `
  -InstallSkills
```

This installs the official CLI and opens the official browser sign-in. It does not generate media or approve spend.

The managed-render gate remains incomplete until one real shot has:

- an approved local source candidate and prompt;
- an exact quote and explicit Admin spend approval;
- a stable Higgsfield request/generation identity;
- a downloaded output in the canonical artifact store;
- checksum and media metadata;
- provider/model/terms/cost evidence;
- human continuity and quality review.

## Live publishing

Live platform credentials remain outside Git and PostgreSQL. A platform target may be activated only after:

- the exact platform and account are selected;
- official OAuth/app credentials are configured outside Git;
- a private or unlisted test upload succeeds;
- the platform reference and status reconcile into the delivery record;
- duplicate and idempotency tests pass;
- a human Super Admin or Admin explicitly authorizes the final public action.

Until that evidence exists, use the approved release export and record the manually published external result. Never mark a simulated delivery as a real publication.

## P100 four-item acceptance

The platform is not generally released until the real controlled pilot contains:

- Rawr Nation local item;
- Rawr Nation managed-render item;
- Animal X local item;
- Animal X managed-render item;
- one script, narration and visual revision cycle for every item;
- complete QA and immutable release package for every item;
- simulated staging delivery for every item;
- one separately approved external live result;
- Super Admin/Admin, Reviewer and delivery decision evidence;
- backup/restore, worker restart and current-runbook drill evidence;
- zero unresolved major or critical defects.

Do not create placeholder evidence or close the P100 issue before these records exist.

## Six-video benchmark

The quality benchmark remains three Rawr Nation and three Animal X vertical videos. Each requires:

- original concept and script;
- factual source review;
- rights and model/provider terms evidence;
- complete narration and captions;
- continuity-approved visual production;
- technical media validation;
- originality-distance review;
- advertiser-suitability and monetization review;
- preserved revisions and final human decision.

Generated media stays outside Git.

## Completion states

### Controlled use ready

- local and remote readiness pass;
- three roles authenticate correctly;
- one browser golden path passes;
- restart persistence passes;
- backup exists.

### Managed production ready

- controlled use ready;
- one real Higgsfield managed shot passes the canonical workflow.

### General production accepted

- managed production ready;
- four-item P100 pilot accepted;
- one external live result recorded;
- no major/critical defects.

### Scaled creative benchmark complete

- six-video Rawr Nation/Animal X batch passes every quality gate.
