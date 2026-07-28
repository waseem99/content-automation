# Local Production Runtime

This runbook operates Creator Studio, PostgreSQL, authenticated operator APIs, durable local queues, Ollama script generation, Kokoro narration, local Whisper alignment, ComfyUI keyframes, FFmpeg narration/MP4 previews, optional approved Higgsfield managed rendering, and private-first YouTube delivery on one Windows workstation.

## Boundaries

- Local generation is the default pre-production path.
- Every script, narration, image, preview, route, release, spend, and delivery decision remains human-controlled.
- Higgsfield is disabled until official account authentication, exact model/pricing/terms configuration, and explicit spend approval.
- YouTube is disabled until official OAuth setup; the initial target is private-only.
- ngrok exposes only the authenticated Creator Studio/API origin.
- PostgreSQL, Ollama, ComfyUI, workers, artifacts, operator keys, models, and credentials remain private.
- Generated media, model files, operator keys, and local configuration remain outside Git.

## Public role model

- **Super Admin** — complete system, environment, credential, user, brand, production, release, and delivery control.
- **Admin** — complete day-to-day platform and content operations.
- **Reviewer** — brand-scoped content creation, script generation/revision, production, narration/visual review, approved-release delivery, and audited archive/supersede actions.

The historical `producer` and `publisher` capability rows remain internal compatibility permissions. They are not separate user-facing accounts. Approved evidence, artifacts, releases, and audit history cannot be permanently deleted through normal operation.

## Prerequisites

1. Windows 10/11 with PowerShell 5.1 or newer.
2. Python 3.11+.
3. Docker Desktop with Linux containers.
4. Ollama for Windows on `127.0.0.1:11434`.
5. ffmpeg on `PATH`.
6. Optional NVIDIA/Docker GPU support for ComfyUI.
7. ngrok Agent for remote team access.
8. Optional Google OAuth client JSON for YouTube.
9. Optional approved Higgsfield account and reviewed pricing/terms evidence.

## Existing workstation upgrade and remote deployment

From an elevated PowerShell in the repository root:

```powershell
git status
git checkout test
git pull --ff-only origin test
```

Do not continue when unknown local code changes are present. Preserve:

```text
.env.local
.runtime/artifacts
.runtime/operator-keys.json
PostgreSQL/Docker volumes
Ollama models
ComfyUI models
```

Configure ngrok once:

```powershell
ngrok config add-authtoken <your-ngrok-token>
```

Deploy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\deploy_remote_content_automation.ps1 `
  -AcceptComfyModelLicense
```

The deployment:

1. preserves PostgreSQL, models, artifacts, queued jobs, reviews, and configuration;
2. applies every migration;
3. preserves the original Admin secret by promoting it to Super Admin;
4. creates separate Admin and Reviewer identities;
5. deactivates old local Producer and Publisher identities;
6. installs application, Kokoro, and `faster-whisper` dependencies;
7. verifies Ollama and the configured local model;
8. starts the API and supervised workers;
9. exposes only the authenticated Creator Studio/API port through ngrok;
10. records readiness and the HTTPS URL outside Git.

Generated files:

```text
.runtime/operator-keys.json
.runtime/remote-access.json
.runtime/production-readiness.json
```

Run the readiness report:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\check_production_readiness.ps1 `
  -RequireRemoteAccess
```

Share only the intended Admin or Reviewer key and the HTTPS Creator Studio URL. Never share the Super Admin key.

## Local-only startup

For local testing without ngrok:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

Open:

```text
http://127.0.0.1:8000/app/dashboard
```

## Creator Studio routes

- Dashboard — attention, reviews, running jobs, failures, and bounded queue controls.
- Content — searchable real records and one clear next action.
- Create content — guided brief and local script generation.
- Reviews — role-scoped script and media decisions.
- Release & delivery — approved packages, simulated delivery, and configured official targets.
- Team & access — Super Admin/Admin public role and key management.
- Settings — brand, voice, local model, ideas, and renderer configuration.
- Operations — runtime recovery, releases, delivery, and P100 controls.

Refreshing a nested `/app/...` route returns the same application shell. Production mode must never fall back to demo data.

## Bounded local queue

Reviewer and Admin users can operate the bounded local queue for their assigned brands.

- **Generate more scripts** enqueues 1–20 eligible script jobs.
- **Continue approved locally** initializes only missing audio/visual work for approved scripts.
- MP4 previews queue only after narration and visuals are approved.
- The controls never auto-approve, reserve spend, deliver, or publish.

## Browser golden path

Use one disposable internal content item before client work.

### Script

1. Sign in as Reviewer or Admin.
2. Open **Create content**.
3. Choose an assigned brand.
4. Enter title/topic, objective, audience, platform, format, duration, language, schedule, and notes.
5. Select **Create and generate script**.
6. Observe the queued/running/succeeded state.
7. Open **Script** and submit the exact draft for review.
8. Record one requested change with a specific rationale.
9. Generate or edit the corrected revision.
10. Approve the corrected exact version.

### Narration and visuals

1. Open **Production** and select **Start local production**.
2. Kokoro narration and ComfyUI keyframes run as background jobs.
3. Play each narration take and select one passing take per paragraph.
4. Regenerate only paragraphs that need pronunciation, pace, or tone correction.
5. Build and play the local narration mix.
6. Preserve one narration revision.
7. Select one visual candidate per scene.
8. Preserve one visual revision.
9. Approve narration and visuals.
10. The continuation/preview workers assemble the FFmpeg MP4.
11. Play or export the complete MP4.
12. Complete technical QA and approve the immutable release package when permitted.

No model action depends on keeping the browser open. Queue state and attempts survive refresh, sign-out, API restart, and workstation restart.

## Open-source text generation

The local concept and script adapters use:

```text
http://127.0.0.1:11434
```

The model is configured by `OLLAMA_MODEL` in `.env.local`. Local-model failure never authorizes paid generation or automatic approval.

## Local narration and alignment

After exact script approval, the P90 service initializes paragraph-bound Kokoro jobs. The aligned worker:

- claims only approved narration work;
- generates local WAV files with Kokoro;
- runs local `faster-whisper` recognition;
- anchors the known script to measured word-time evidence;
- validates coverage, order, and monotonic timing;
- registers authenticated internal review assets;
- records zero external cost;
- preserves script/preset lineage;
- leaves final approval blocked until human review.

Default settings:

```env
LOCAL_ALIGNMENT_ENABLED=true
LOCAL_ALIGNMENT_MODEL_ID=tiny
LOCAL_ALIGNMENT_DEVICE=cpu
LOCAL_ALIGNMENT_COMPUTE_TYPE=int8
LOCAL_ALIGNMENT_MINIMUM_COVERAGE=0.72
```

When Whisper is unavailable or validation fails, proportional preview timings remain playable but cannot satisfy final narration approval.

## Local ComfyUI keyframes

One-time setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_p68_local_keyframe_worker.ps1 `
  -AcceptModelLicense
```

Configure `.env.local`:

```env
P68_COMFYUI_WORKFLOW_PATH=<absolute path to reviewed ComfyUI API workflow JSON>
P68_COMFYUI_CHECKPOINT=sd_xl_base_1.0.safetensors
P68_COMFYUI_BASE_URL=http://127.0.0.1:8188
```

Restart the runtime. Format/corruption checks are automated; creative, continuity, framing, subject, palette, and lighting remain human decisions.

## Automated API smoke

After startup:

```powershell
$env:LOCAL_ADMIN_OPERATOR_KEY = "<admin-key>"
.\.venv\Scripts\python.exe .\scripts\local_golden_path_smoke.py
```

The smoke uses the real API, PostgreSQL, active profiles, local Ollama adapter, workflow, and durable queue. It creates no paid spend, delivery, or publication evidence. Browser acceptance remains required for the complete workflow.

## Official YouTube setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_youtube_official.ps1 `
  -GoogleOAuthClientJson "C:\secure\youtube-client.json" `
  -ChannelReference "channel:<channel-id-or-name>"
```

The loopback OAuth flow stores its refresh token outside Git and PostgreSQL with restricted Windows ACLs. Setup creates a private-only target and does not upload automatically.

A real proof requires:

- an approved immutable release;
- checksum/size/MIME verification;
- explicit human delivery action;
- successful private upload;
- recorded YouTube video ID and reconciled status;
- idempotency and duplicate protection.

Public or unlisted visibility remains disabled until the private proof is accepted and the target is explicitly revised by an authorized administrator.

## Official Higgsfield setup

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

Setup authenticates the official CLI, records the exact account-visible model and reviewed commercial evidence, and enables the isolated worker. It does not generate media or spend credits.

A real managed shot requires:

- an approved local source candidate and prompt;
- exact quote and Admin spend approval;
- stable provider generation identity;
- restart-safe polling without duplicate submission;
- downloaded canonical artifact with checksum/media metadata;
- model, terms, lineage, and cost reconciliation;
- human continuity and quality review.

## Restart and persistence proof

After completing a disposable golden-path item:

1. Stop the runtime cleanly.
2. Restart the scheduled/always-on service.
3. Refresh Creator Studio.
4. Confirm content, revisions, reviews, jobs, artifacts, and release state remain.
5. Confirm completed jobs were not duplicated.
6. Confirm the ngrok URL/readiness file is refreshed when remote deployment is used.

## Logs and recovery

```text
.runtime/logs/supervisor.log
.runtime/logs/api.log
.runtime/logs/api.error.log
.runtime/logs/text-audio-worker.log
.runtime/logs/text-audio-worker.error.log
.runtime/logs/visual-worker.log
.runtime/logs/visual-worker.error.log
.runtime/logs/preview-worker.log
.runtime/logs/preview-worker.error.log
.runtime/logs/continuation.log
.runtime/logs/continuation.error.log
.runtime/logs/higgsfield-worker.log
.runtime/logs/higgsfield-worker.error.log
.runtime/supervisor-heartbeat.json
```

Queued jobs use leases, retries, stale-worker recovery, immutable attempts, and idempotency keys. Restarting the API or worker does not erase PostgreSQL, models, queues, or artifacts.

Stop services while preserving data:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\stop_local_production.ps1
```

Stop API/workers/ngrok while leaving PostgreSQL running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\stop_local_production.ps1 `
  -KeepDatabase
```

## P100 controlled pilot

Super Admin/Admin Operations exposes canonical candidate discovery, four bounded slots, exactly one external live-result evidence item, controlled draft bootstrap, readiness, and digest-guarded start.

The required split is:

- Rawr Nation local item;
- Rawr Nation managed item;
- Animal X local item;
- Animal X managed item.

The pilot remains incomplete until all four items have the required script/narration/visual revisions, QA, releases, staging delivery, role decisions, one external result, restart/restore/runbook evidence, and zero unresolved major/critical defects.

Daily local content production does not depend on starting P100.

## Intentionally blocked

- Automatic final approval.
- Automatic public publishing.
- Paid generation without explicit human spend approval.
- Public YouTube visibility before the private proof and explicit target revision.
- General production rollout before the P100 four-item acceptance pilot passes.
