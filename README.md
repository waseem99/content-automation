# Content Automation Platform

A local-first, multi-brand content production system. PostgreSQL is the only workflow/state system of record; generated media is stored on the local workstation and optional Google Drive locations.

## Current production model

```text
native campaign
→ database validation and activation
→ automatic concept/script/source production
→ automatic policy checks and routine approval
→ narration, scene, caption and platform planning
→ grouped hard blockers only
→ immutable ready-for-final-video-generation package
→ local GPU / deterministic / manual render execution
→ human creative review
→ final QA and immutable release
→ explicit delivery or publishing action
```

The central pre-generation ecosystem has passed its staged acceptance gates for 10,000 campaign items, 1,000 automatic pre-generation items, 1,000,000 checks/tasks, 100 workers, 100,000 local/Drive locations and 1,000-item mass operations. Real 10,000–20,000 completed-video monthly renderer capacity is not yet proven.

See [Final staged acceptance report](docs/operations/P131_FINAL_ACCEPTANCE_REPORT.md).

## Immediate production objective

The active workstream is [#833 — Local GPU production and low-cost hybrid rendering](https://github.com/waseem99/content-automation/issues/833).

Execution order:

1. [#828](https://github.com/waseem99/content-automation/issues/828) — validate the actual ComfyUI/Wan2.2 workstation package and produce the first reviewed local MP4 with zero external fee.
2. [#827](https://github.com/waseem99/content-automation/issues/827) — run the measured 30-attempt / three-video workstation calibration.
3. [#829](https://github.com/waseem99/content-automation/issues/829) — complete reusable templates and deterministic composition execution.
4. [#832](https://github.com/waseem99/content-automation/issues/832) — measure batch capacity, QA and cost per accepted video.
5. [#830](https://github.com/waseem99/content-automation/issues/830) and [#831](https://github.com/waseem99/content-automation/issues/831) — add cloud or premium overflow only after local evidence.

Use [Local GPU activation](docs/operations/LOCAL_GPU_ACTIVATION.md) for the first workstation proof.

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
- Local and Google Drive asset locations with checksum reconciliation and recovery.
- Renderer catalogue, routing evidence, quotes, spend reservations and cost lineage.
- Final QA, immutable releases, simulated delivery and private-first YouTube support.

## Deliberately blocked by default

- Automatic paid generation.
- Automatic final creative approval.
- Automatic public publishing.
- Browser automation, copied provider sessions or undocumented endpoints.
- Treating database throughput as real GPU rendering throughput.

## Start locally

Prerequisites: Windows 10/11, Python 3.11+, Docker Desktop, Ollama, ffmpeg and optional NVIDIA/ComfyUI support.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

Open `http://127.0.0.1:8000/app/dashboard`.

For authenticated remote access:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\deploy_remote_content_automation.ps1 `
  -AcceptComfyModelLicense
```

Only Creator Studio/API may be exposed. PostgreSQL, Ollama, ComfyUI, workers, artifacts, models and credentials remain private.

## Repository map

```text
src/application/          production domain services
src/operator_api/         authenticated API and Creator Studio serving
src/operations/           workers, onboarding, recovery and acceptance tools
web/static-creator-ui/    browser application
migrations/               append-only PostgreSQL migrations
scripts/windows/          workstation deployment and validation
deploy/                   worker packaging
docs/operations/          operator runbooks and acceptance evidence
```

Generated media, models, credentials, environment files and operator keys remain outside Git. Legacy clip-extraction and experimental pipelines are reference-only unless a current runbook explicitly invokes them.
