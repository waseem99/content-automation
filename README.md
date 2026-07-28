# Content Automation Platform

A local-first, multi-brand content operating system for concept generation, script and source review, narration, visual production, human revisions, spend control, final QA, release packaging, controlled delivery, and performance learning.

The current production line is P84–P107. Earlier football clip-extraction and experimental runners remain in the repository as legacy/reference pipelines, but they are not the primary operator workflow.

## Current operating model

```text
brand setup
→ guided content brief or approved idea
→ local script generation
→ source and claim review
→ local Kokoro narration with local Whisper word alignment
→ local ComfyUI keyframes and deterministic motion
→ human narration and visual review
→ optional approved Higgsfield managed-shot routing
→ final assembly and technical QA
→ immutable package approval
→ simulated delivery or approved private-first YouTube delivery
→ external result evidence
→ analytics and production economics
```

## Public role model

Creator Studio exposes only three user-facing roles:

- **Super Admin** — system, environment, credentials, role, brand, production, release, and delivery control.
- **Admin** — complete day-to-day content, production, review, spend, release, delivery, brand, and user management.
- **Reviewer** — brand-scoped content creation, script generation/revision, production, narration/visual review, approved-release delivery, and audited archive/supersede actions.

The historical `producer` and `publisher` capabilities remain internal compatibility permissions. They are not separate user-facing accounts. Permanent deletion of approved evidence, artifacts, releases, or audit history remains prohibited.

## Creator Studio v2

The production browser application is a routed, role-aware workspace rather than one technical page.

```text
/app/dashboard                 attention, reviews, active jobs, and failures
/app/content                   searchable content library
/app/content/new               guided Create Content workflow
/app/content/{id}/script       script evidence and exact-version review
/app/content/{id}/production   local and managed generation jobs, progress, and retry
/app/content/{id}/media        narration, visual, and MP4 review
/app/reviews                   role-scoped review inbox
/app/publishing                approved release and delivery workspace
/app/team                      Super Admin/Admin team and role-key management
/app/settings                  brand, voice, model, idea, and renderer settings
/app/operations                runtime recovery, releases, delivery, and P100
```

Normal production does not ask for raw UUIDs, JSON payloads, fixed seeds, or direct database edits. The browser displays the real workflow status, permitted next action, human-readable blocker, and background job state for every content item.

## Implemented

- PostgreSQL-backed multi-brand plans, content, versions, artifacts, reviews, releases, and analytics.
- Super Admin, Admin, and Reviewer public roles with brand assignments.
- Versioned brand profiles, approved voices, and narration presets.
- Local Ollama-compatible concept and script adapters with deterministic fallback.
- P87 restart-safe generation queue.
- Local Kokoro narration jobs with local `faster-whisper` script-anchored word alignment.
- Preview-only timing fallback that cannot satisfy final narration approval.
- Local FFmpeg narration mixes and deterministic MP4 previews.
- Local ComfyUI keyframe candidates.
- Human comments, change requests, comparisons, approvals, and preserved revisions.
- Renderer catalogue, quotes, explicit spend reservations, and cost reconciliation.
- Official Higgsfield CLI worker for approved managed shots.
- Shared artifact storage, immutable release manifests, and final technical QA.
- Simulated delivery and external live-result evidence.
- Official OAuth-backed YouTube delivery, private by default.
- Operations, backup/restore evidence, readiness, and the bounded P100 pilot.
- Authenticated ngrok remote access exposing only Creator Studio/API.
- Secure authenticated playback for local audio, image, narration-mix, and MP4 outputs.

## Deliberately blocked by default

- Automatic final approval.
- Automatic public publishing.
- Paid generation without an exact quote and explicit human spend approval.
- Browser automation, copied provider sessions, or undocumented provider endpoints.
- Public YouTube visibility until a private proof succeeds and the target is explicitly revised.
- General rollout before the four-item P100 acceptance pilot passes.
- Vercel media processing.

## Start locally

Windows prerequisites:

- Python 3.11+
- Docker Desktop
- Ollama for Windows
- ffmpeg
- Optional NVIDIA/Docker GPU support for ComfyUI

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

Creator Studio opens at:

```text
http://127.0.0.1:8000/app/dashboard
```

Public role keys are generated outside Git at:

```text
.runtime/operator-keys.json
```

Share only the intended Admin or Reviewer key. Never share the Super Admin key.

## Deploy for authenticated remote use

Configure ngrok once:

```powershell
ngrok config add-authtoken <your-ngrok-token>
```

Then deploy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\deploy_remote_content_automation.ps1 `
  -AcceptComfyModelLicense
```

Validate:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\check_production_readiness.ps1 `
  -RequireRemoteAccess
```

Only the authenticated Creator Studio/API origin is exposed. PostgreSQL, Ollama, ComfyUI, artifacts, operator keys, and worker ports remain private.

## Browser golden path

```text
Login as Reviewer or Admin
→ Create content from a manual brief
→ Generate local script
→ Submit exact script version for review
→ Preserve one requested-change revision
→ Approve the corrected script
→ Start narration and visual production
→ Select narration takes and build the local mix
→ Preserve one narration revision
→ Select visual candidates and preserve one visual revision
→ Approve narration and visuals
→ Generate and play the MP4 preview
→ Complete technical QA and release approval
```

Every model operation returns a background job immediately. Queued, running, succeeded, failed, cancelled, and retried states remain visible after browser refresh and workstation restart.

## Local smoke

```powershell
$env:LOCAL_ADMIN_OPERATOR_KEY = "<admin-key>"
.\.venv\Scripts\python.exe .\scripts\local_golden_path_smoke.py
```

The smoke exercises the real API, PostgreSQL, brand profile, local Ollama adapter, workflow initialization, and queue state. It creates no approval, paid spend, delivery, or publication evidence.

## Official external integrations

### YouTube

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_youtube_official.ps1 `
  -GoogleOAuthClientJson "C:\secure\youtube-client.json" `
  -ChannelReference "channel:<channel-id-or-name>"
```

The initial delivery target is private-only. Setup authorizes the account but does not upload automatically.

### Higgsfield

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_higgsfield_official.ps1 `
  -ModelKey "<official-model-key>" `
  -ModelDisplayName "<model-name>" `
  -PricePerSecondUsd <reviewed-price> `
  -UsageTermsUrl "<official-terms-url>" `
  -UsageEvidenceFile "C:\secure\higgsfield-terms-evidence.txt" `
  -InstallSkills
```

Setup authenticates and configures the worker. It does not generate media or approve spend.

## Repository map

```text
src/application/          domain services for concepts, scripts, audio, visuals, routing, releases, delivery, analytics, acceptance
src/operator_api/         authenticated FastAPI routes and production Creator Studio serving
src/operations/           local onboarding, queue workers, alignment, operations and recovery
web/static-creator-ui/    routed role-aware browser application
migrations/               append-only PostgreSQL schema migrations
scripts/windows/          local/remote workstation launch, readiness, provider and recovery scripts
deploy/                   local and managed worker packaging
docs/operations/          non-developer runbooks
```

See [Production activation](docs/operations/PRODUCTION_ACTIVATION.md), [Local Production Runtime](docs/operations/LOCAL_PRODUCTION_RUNBOOK.md), and [Creator Studio v2](docs/operations/CREATOR_STUDIO_V2.md).

## Development validation

Focused changes must compile and test against their exact branch head. Production-mode UI must never silently fall back to demo records. Generated media, models, environment files, operator keys, cookies, and credentials must remain outside Git.

## Legacy pipelines

Legacy clip extraction and explainer commands remain available in `src.cli`, `concepts/`, and `video-engine/`. Use them only when a documented production workflow explicitly references them; new multi-brand work should enter through Creator Studio and the PostgreSQL-backed pipeline.
