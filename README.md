# Content Automation Platform

A local-control, provider-capable, multi-brand content production system. PostgreSQL is the only workflow/state system of record; generated media is stored on the controlled workstation and optional Google Drive locations.

## Current production model

```text
native campaign
→ database validation and activation
→ automatic concept/script/source production
→ automatic policy checks and routine approval
→ narration, scene, caption and platform planning
→ grouped hard blockers only
→ immutable ready-for-final-video-generation package
→ deterministic composition plus approved managed video generation
→ human creative review
→ final QA and immutable release
→ explicit delivery or publishing action
```

The central pre-generation ecosystem has passed its staged acceptance gates for 10,000 campaign items, 1,000 automatic pre-generation items, 1,000,000 checks/tasks, 100 workers, 100,000 local/Drive locations and 1,000-item mass operations. Real high-volume completed-video throughput is not yet proven.

See [Final staged acceptance report](docs/operations/P131_FINAL_ACCEPTANCE_REPORT.md).

## Immediate production objective

The active workstream is provider-first video production because the current 8 GB workstation cannot run the approved 24 GB-class Wan2.2 proof safely.

Execution order:

1. Configure official fal and Vidu accounts, exact pricing and usage evidence without spending credits.
2. Produce one canonical internal provider-generated MP4 through the existing P87/P93/P94 controls.
3. Run at least 30 attempts and complete three pilot videos with measured quality, latency and cost.
4. Complete reusable composition templates and deterministic editing.
5. Run a six-video creative pilot, then 20-video and 40–50-video measured batches.
6. Add self-hosted cloud GPU or rare premium hero routes only where measured economics justify them.

Use [Provider-first video production](docs/operations/PROVIDER_FIRST_VIDEO_PRODUCTION.md) for activation. The existing [Local GPU activation](docs/operations/LOCAL_GPU_ACTIVATION.md) remains an optional future cost-optimization path, not a production dependency.

## Governance continuity

The proven **P84–P107** Creator Studio, workflow, review, routing, spend, storage, release and delivery chain remains authoritative. Provider-first execution changes the rendering engine, not the control plane or its human gates.

- **#833 — Local GPU production and low-cost hybrid rendering** remains the parent governance record while its execution strategy is updated to provider-first production.
- **#828** remains open/deferred because no canonical local 24 GB GPU MP4 has been produced; it is not being represented as complete.
- **#827** remains the calibration gate, now requiring measured provider attempts and completed pilot videos before scale claims.
- `LOCAL_GPU_ACTIVATION.md` remains retained for a future approved local or self-hosted cost-optimization experiment.

## Public roles

- **Super Admin** — system, environment, credentials, roles and infrastructure.
- **Admin** — complete day-to-day brand and production operations.
- **Reviewer** — brand-scoped creation, production, review and approved workflow progression.

Historical Producer and Publisher permissions remain internal capabilities only.

## Creator Studio

```text
/app/dashboard       campaign health, exceptions, jobs and failures
/app/campaigns       native campaign creation, activation and large-scale operations
/app/content         searchable canonical content library
/app/reviews         grouped and item-level review queues
/app/publishing      approved release and delivery workspace
/app/team            role and brand access
/app/settings        brands, voices, models, renderers and policies
/app/operations      runtime, recovery and acceptance controls
```

Normal production must not require spreadsheets, raw UUID entry or direct database edits.

## Implemented

- PostgreSQL-native campaigns, immutable versions, item events and mass operations.
- Automatic pre-generation and grouped exception handling.
- Renderer-ready packages with exact shot timings, prompts, negative constraints, continuity bindings, narration segments, captions and output adaptations.
- Restart-safe jobs, DAG tasks, attempts, leases, retries and idempotency.
- Local Ollama-compatible scripts, Kokoro narration, Whisper alignment, ComfyUI keyframes and FFmpeg assembly.
- Official managed-render execution for fal and Vidu with exact spend reservation, request-ID recovery, immediate checksum ingestion and pending human review.
- Existing official Higgsfield specialist route under separate account/model/terms activation.
- Local and Google Drive asset locations with checksum reconciliation and recovery.
- Renderer catalogue, routing evidence, quotes, spend reservations and cost lineage.
- Final QA, immutable releases, simulated delivery and private-first YouTube support.

## Deliberately blocked by default

- Paid provider execution until explicitly enabled after account, pricing, terms and budget review.
- Automatic final creative approval.
- Automatic public publishing.
- Browser automation, copied provider sessions or undocumented endpoints.
- Treating database throughput as real video-production throughput.

## Start locally

Prerequisites: Windows 10/11, Python 3.11+, Docker Desktop, Ollama and ffmpeg. NVIDIA/ComfyUI is optional for keyframes or future local video optimization.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

Open `http://127.0.0.1:8000/app/dashboard`.

For authenticated remote access:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\deploy_remote_content_automation.ps1 `
  -SkipComfyUI `
  -SkipInstall `
  -SkipModelPull
```

Only Creator Studio/API may be exposed. PostgreSQL, Ollama, ComfyUI, provider workers, artifacts, models and credentials remain private.

## Repository map

```text
src/application/          production domain services and provider adapters
src/operator_api/         authenticated API and Creator Studio serving
src/operations/           workers, onboarding, recovery and acceptance tools
web/static-creator-ui/    browser application
migrations/               append-only PostgreSQL migrations
scripts/windows/          workstation deployment and provider activation
deploy/                   worker packaging
config/                   non-secret runtime examples and workflow manifests
docs/operations/          operator runbooks and acceptance evidence
```

Generated media, models, credentials, environment files and operator keys remain outside Git. Legacy clip-extraction and experimental pipelines are reference-only unless a current runbook explicitly invokes them.
