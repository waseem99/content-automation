# Content Automation Platform

A local-first, multi-brand content operating system for concept generation, script and source review, narration, visual production, human revisions, spend control, final QA, release packaging, delivery evidence, and performance learning.

The current production line is P84–P100. Earlier football clip-extraction and experimental runners remain in the repository as legacy/reference pipelines, but they are not the primary operator workflow.

## Current operating model

```text
brand setup
→ guided content brief or approved idea
→ local script generation
→ source and claim review
→ local Kokoro narration
→ local ComfyUI keyframes and deterministic motion
→ human visual review and revision
→ optional managed-shot routing
→ final assembly and technical QA
→ package approval
→ simulated delivery / external result evidence
→ analytics and production economics
```

## Creator Studio v2

The production browser application is a routed, role-aware workspace rather than one technical page.

```text
/app/dashboard                 attention, reviews, active jobs, and failures
/app/content                   searchable content library
/app/content/new               guided Create Content workflow
/app/content/{id}/script       script evidence and exact-version review
/app/content/{id}/production   local generation jobs, progress, and retry
/app/content/{id}/media        narration, visual, and MP4 review
/app/reviews                   Reviewer inbox
/app/publishing                Publisher release and delivery workspace
/app/team                      Admin team and role-key management
/app/settings                  brand, voice, model, idea, and renderer settings
/app/operations                runtime recovery, releases, delivery, and P100
```

Normal production does not ask for raw UUIDs, JSON payloads, fixed seeds, or PowerShell commands. The browser displays the real workflow status, permitted next action, human-readable blocker, and background job state for every content item.

## Implemented

- PostgreSQL-backed multi-brand plans, content, versions, artifacts, reviews, releases, and analytics.
- Admin, Producer, Reviewer, and Publisher roles with brand assignments.
- Versioned brand profiles, approved voices, and narration presets.
- Local Ollama-compatible concept and script adapters with deterministic fallback.
- P87 restart-safe generation queue.
- Local Kokoro narration jobs.
- Local ComfyUI keyframe candidates.
- Human comments, change requests, comparisons, approvals, and preserved revisions.
- Renderer catalogue, quotes, spend reservations, and cost reconciliation.
- Shared artifact storage, immutable release manifests, final technical QA.
- Simulated delivery and external live-result evidence.
- Operations, backup/restore evidence, readiness, and the bounded P100 pilot.
- Secure authenticated playback for local audio, image, and MP4 job outputs.

## Deliberately disabled

- Automatic final approval.
- Automatic live publishing.
- Paid generation without explicit approval.
- Browser automation or copied provider sessions.
- Higgsfield or another real managed renderer until a supported account integration is configured.
- Vercel media processing.

## Start the complete local runtime

Windows prerequisites:

- Python 3.11+
- Docker Desktop
- Ollama for Windows
- ffmpeg
- Optional NVIDIA/Docker GPU support for ComfyUI
- Optional ngrok for remote review

Start:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

Creator Studio opens at:

```text
http://127.0.0.1:8000/app/dashboard
```

Role-specific keys are generated outside Git at:

```text
.runtime/operator-keys.json
```

Admin users can copy Producer, Reviewer, and Publisher keys from **Team & access**. The browser never reveals the Admin key.

Start with remote team review:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1 `
  -ExposeWithNgrok
```

Only the authenticated Creator Studio/API port is exposed. PostgreSQL, Ollama, ComfyUI, artifacts, and worker ports remain local.

See [Local Production Runtime](docs/operations/LOCAL_PRODUCTION_RUNBOOK.md) and [Creator Studio v2](docs/operations/CREATOR_STUDIO_V2.md).

## Browser golden path

```text
Login
→ Create content
→ Generate local script
→ Submit for review
→ Reviewer approves exact version
→ Start local narration and visuals
→ Review and approve media
→ Generate MP4 preview
→ Play or export preview
```

Every model operation returns a background job immediately. Queued, running, succeeded, failed, cancelled, and retried states remain visible after browser refresh.

## Local smoke

```powershell
$env:LOCAL_ADMIN_OPERATOR_KEY = "<admin-key>"
.\.venv\Scripts\python.exe .\scripts\local_golden_path_smoke.py
```

The smoke exercises the real API, PostgreSQL, brand profile, local Ollama adapter, workflow initialization, and queue state. It creates no approval, paid spend, delivery, or publication evidence.

## Repository map

```text
src/application/          domain services for concepts, scripts, audio, visuals, routing, releases, delivery, analytics, acceptance
src/operator_api/         authenticated FastAPI routes and production Creator Studio serving
src/operations/           local onboarding, queue worker, operations and recovery
web/static-creator-ui/    routed role-aware browser application
migrations/               append-only PostgreSQL schema migrations
scripts/windows/          local workstation launch/stop and P68 GPU setup
deploy/                   local/managed worker packaging
docs/operations/          non-developer runbooks
```

## Development validation

Focused changes must compile and test against their exact branch head. Production-mode UI must never silently fall back to demo records. Generated media, models, environment files, operator keys, cookies, and credentials must remain outside Git.

## Legacy pipelines

Legacy clip extraction and explainer commands remain available in `src.cli`, `concepts/`, and `video-engine/`. Use them only when a documented production workflow explicitly references them; new multi-brand work should enter through Creator Studio and the PostgreSQL-backed pipeline.
