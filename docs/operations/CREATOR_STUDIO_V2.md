# Creator Studio v2

Creator Studio v2 is the role-aware browser application for the local content production runtime. It replaces the legacy single-page console with task-oriented routes while preserving PostgreSQL, workflow, queues, Ollama, Kokoro, ComfyUI, FFmpeg, managed rendering, review, release, delivery, analytics, and acceptance services.

## Entry points

Local:

```text
http://127.0.0.1:8000/app/dashboard
```

Remote team access uses the authenticated HTTPS address recorded by the reviewed ngrok deployment workflow. Never expose PostgreSQL, Ollama, ComfyUI, worker ports, artifacts, or operator-key files.

## Public roles

Creator Studio exposes only three public roles:

- **Super Admin** — system, environment, credentials, roles, brands, production, release, and delivery control.
- **Admin** — complete day-to-day platform administration and content operations.
- **Reviewer** — brand-scoped content creation, script generation/revision, local production, media review, approved-release delivery, and audited archive/supersede actions.

The historical `producer` and `publisher` capability rows remain internal compatibility permissions. They are not separate user-facing roles. Permanent deletion of approved evidence, artifacts, releases, or audit history remains prohibited.

## Navigation

- **Dashboard** — attention items, review counts, active jobs, failures, and bounded queue controls.
- **Content** — searchable real content records with one clear next action per item.
- **Create content** — guided brand, starting-point, brief, and confirmation flow.
- **Reviews** — role-scoped script, narration, visual, and preview decisions.
- **Release & delivery** — approved release packages, simulated delivery, and configured official targets.
- **Team & access** — Super Admin/Admin public role, brand assignment, and local key management.
- **Settings** — brand profiles, approved voices, local models, idea generation, and renderer status.
- **Operations** — Super Admin/Admin queue recovery, runtime monitoring, releases, delivery, and P100 controls.

## Daily golden path

### Reviewer or Admin

1. Open **Create content**.
2. Choose Rawr Nation, Animal X, or another assigned brand.
3. Choose a starting point.
4. Enter the topic, objective, audience, format, duration, language, schedule, and optional notes.
5. Confirm **Create and generate script**.
6. The browser returns immediately with a queued local Ollama job.
7. Open the content workspace to see queued, running, succeeded, failed, or retried state.
8. Review the generated draft and submit the exact version for review.
9. Record a specific approval, requested change, or rejection rationale.
10. Preserve one corrected script revision when testing the full workflow.
11. After script approval, open **Production** and select **Start local production**.
12. Kokoro narration and ComfyUI keyframes run as background jobs.
13. Play narration takes, select one passing take per paragraph, and regenerate only affected paragraphs.
14. Build and review the local narration mix.
15. Select visual candidates and preserve any requested visual revision.
16. Approve narration and visuals.
17. The continuation and preview workers queue the FFmpeg MP4.
18. Play or export the resulting preview from **Media review**.
19. Complete technical QA and approve the immutable release package when permitted.

No model action depends on keeping the browser open. Queue state and attempts survive refresh, sign-out, API restart, and workstation restart.

## P100 controlled pilot sequence

P100 controls remain under **Operations** and are restricted to Super Admin/Admin in the normal browser workflow.

1. Select exactly one local and one managed item for Rawr Nation.
2. Select exactly one local and one managed item for Animal X.
3. Confirm that all four content records and versions are unique.
4. Choose the single item that requires external live-result evidence.
5. Select **Create controlled draft**.
6. Review controlled-start readiness. The start button remains disabled while any canonical blocker exists.
7. Select **Start controlled pilot** only after every start check passes.
8. Refresh the four-item evidence snapshot throughout execution.
9. Resolve real blockers in the underlying content, review, spend, release, delivery, restart, backup, or runbook evidence.
10. Record the exact canonical snapshot only after the backend preview passes.
11. Complete independent Super Admin/Admin/Reviewer decisions and exactly one separately approved external result.
12. Accept only with a unique `prod-*` label and the current packaged runbook digest.

P100 snapshot operations do not fabricate media, approvals, spend, delivery, operational drills, or final acceptance.

## Official integrations

### Higgsfield

The managed-render worker is available only after official CLI authentication, exact model/pricing/terms configuration, a quote, and explicit human spend approval. Completed outputs enter the canonical artifact store as pending human review.

### YouTube

The official OAuth-backed delivery target is private by default. Every real upload still requires an approved immutable release and explicit human action. Public or unlisted visibility remains blocked until the private proof is accepted and the target is deliberately revised.

## Status and blockers

The browser does not independently guess eligibility. The orchestration API returns:

- current user-facing status;
- one or more permitted next actions;
- human-readable blockers;
- real generation jobs and attempts;
- existing script, narration, visual, preview, release, and delivery records.

Failed jobs expose the backend error and can be retried without duplicating successful work.

## Local access keys

Public keys are stored outside Git in:

```text
.runtime/operator-keys.json
```

Super Admin/Admin can manage the public Admin and Reviewer identities through **Team & access**. The Super Admin key must never be shared with ordinary users or exposed through the browser.

## Safety boundaries

- No automatic final approval.
- No automatic public publishing.
- No paid generation without an exact quote and explicit spend approval.
- No browser cookies, private provider endpoints, or desktop macro automation.
- Job media can be read only after operator authentication and brand-scope authorization.
- Local media paths are restricted to `LOCAL_ARTIFACT_ROOT`.
- P100 evidence snapshots use canonical backend checks and exact identity matching; the browser cannot submit operator-supplied pass flags.

## Routed URLs

```text
/app/dashboard
/app/content
/app/content/new
/app/content/{content_id}
/app/content/{content_id}/script
/app/content/{content_id}/production
/app/content/{content_id}/media
/app/content/{content_id}/history
/app/reviews
/app/publishing
/app/team
/app/settings
/app/operations
```

Refreshing a nested route returns the same application shell; API endpoints remain separate under their existing paths.
