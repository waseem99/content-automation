# Creator Studio v2

Creator Studio v2 is the role-aware browser application for the local content production runtime. It replaces the legacy single-page console with task-oriented routes while preserving the existing PostgreSQL, workflow, queue, Ollama, Kokoro, ComfyUI, FFmpeg, review, release, and acceptance services.

## Entry point

Open:

```text
http://127.0.0.1:8000/app/dashboard
```

The same authenticated application can later be exposed through the reviewed ngrok workflow. Do not expose PostgreSQL, Ollama, ComfyUI, or worker ports.

## Navigation

- **Dashboard** — attention items, review counts, active jobs, failures, and recent content.
- **Content** — searchable real content records with one clear next action per item.
- **Create content** — guided brand, starting-point, brief, and confirmation flow.
- **Reviews** — role-scoped script, narration, visual, and preview decisions.
- **Team & access** — Admin-only role, brand assignment, and local role-key management.
- **Settings** — brand profiles, approved voices, local models, idea generation, and renderer status.
- **Operations** — Admin-only queue recovery, runtime monitoring, releases, delivery, and P100 controls.

## Daily golden path

### Producer or Admin

1. Open **Create content**.
2. Choose Rawr Nation or Animal X.
3. Choose a starting point.
4. Enter the topic, objective, audience, format, duration, language, schedule, and optional notes.
5. Confirm **Create and generate script**.
6. The browser returns immediately with a queued local Ollama job.
7. Open the content workspace to see queued, running, succeeded, or failed state.
8. When the draft is ready, review it and select **Submit for review**.

### Reviewer

1. Open **Reviews**.
2. Select the script item.
3. Review exact narration sections, claims, source evidence, and open actions.
4. Enter a specific rationale.
5. Approve the version, request changes, or reject it.

### Local media production

1. After script approval, a Producer or Admin opens **Production**.
2. Select **Start local production**.
3. Kokoro narration and ComfyUI keyframes run as background jobs.
4. Generated narration and images are playable or viewable under **Media review**.
5. Select one visual candidate per scene and submit the visual project.
6. Submit narration after the current mix is ready.
7. A Reviewer approves narration and the full visual project.
8. The always-on continuation worker queues the FFmpeg MP4 preview.
9. Play or export the resulting preview from **Media review**.

## Status and blockers

The browser does not independently guess eligibility. The Studio v2 orchestration API returns:

- the current user-facing status;
- one or more permitted next actions;
- human-readable blockers;
- real generation jobs and their attempts;
- existing script, narration, visual, and preview records.

Failed jobs expose the backend error and can be retried without duplicating successful work.

## Role behavior

- **Admin** sees all assigned brands and configuration/operations controls.
- **Producer** creates content, runs local generation, submits work, and handles revisions.
- **Reviewer** lands in the review inbox and records exact-version decisions.
- **Publisher** sees approved release and delivery work only.

Normal workflows never request a raw UUID, JSON payload, fixed seed, or internal database identifier.

## Local access keys

The initial workstation still uses operator keys. Admins can copy Producer, Reviewer, and Publisher keys from **Team & access**. The Admin key is deliberately excluded from the browser key-management response.

Keys and local configuration remain outside Git.

## Safety boundaries

- No automatic approval.
- No automatic live publishing.
- No paid generation.
- No managed-render call until the renderer is explicitly connected.
- Job media can be read only after operator authentication and brand-scope authorization.
- Local media paths are restricted to `LOCAL_ARTIFACT_ROOT`.

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
/app/team
/app/settings
/app/operations
```

Refreshing a nested route returns the same application shell; API endpoints remain separate under their existing paths.
