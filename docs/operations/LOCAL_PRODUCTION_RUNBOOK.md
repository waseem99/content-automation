# Local Production Runtime

This runbook operates the multi-brand Creator Studio, PostgreSQL, authenticated operator API, durable local queues, Ollama script generation, Kokoro narration, local Whisper alignment, ComfyUI keyframes, and FFmpeg narration/MP4 previews on one Windows workstation.

## Boundaries

- Local generation is the default.
- Every script, narration, image, preview, route, release, and delivery decision remains human-controlled.
- No Higgsfield or other managed renderer is configured.
- No live social publishing adapter is enabled.
- ngrok exposes the same authenticated Creator Studio/API origin; it does not weaken operator-key or brand-role checks.
- Generated media, model files, operator keys, and local configuration remain outside Git.

## Prerequisites

1. Windows 10/11 with PowerShell 5.1 or newer.
2. Python 3.11+.
3. Docker Desktop with Linux containers.
4. Ollama for Windows, running on `127.0.0.1:11434`.
5. ffmpeg on `PATH`.
6. Optional NVIDIA/Docker GPU support for the existing P68 ComfyUI worker.
7. Optional ngrok Agent when remote team review is required.

## First startup

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1
```

The launcher:

1. Creates `.env.local` when missing.
2. Generates four strong operator keys outside Git.
3. Starts PostgreSQL on loopback port `5434`.
4. Creates `.venv` and installs application, Kokoro, and `faster-whisper` dependencies.
5. Verifies Ollama and pulls the configured open-source model.
6. Applies all PostgreSQL migrations.
7. Idempotently seeds Rawr Nation, Animal X, roles, assignments, profiles, narration presets, visual presets, and safe initial content records.
8. Starts the FastAPI/Creator Studio at `http://127.0.0.1:8000`.
9. Starts the aligned local worker in manual mode, or supervised script/audio, visual, and MP4 workers in always-on mode.

Operator keys are written to:

```text
.runtime/operator-keys.json
```

Share only the key matching the team member’s role. After the initial Admin login, Producer, Reviewer, and Publisher keys can be copied from **Team & access**. The Admin key is deliberately not shown in the browser key-management screen.

## Open Creator Studio

Open:

```text
http://127.0.0.1:8000/app/dashboard
```

The browser application is divided into task-oriented routes:

- Dashboard — attention, reviews, running jobs, failures, and bounded local queue controls.
- Content — searchable real records and one clear next action.
- Create content — guided brief and local script generation.
- Reviews — role-scoped script and media decisions.
- Release & delivery — Publisher workspace.
- Team & access — Admin operator and key management.
- Settings — brand, voice, local model, ideas, and renderer configuration.
- Operations — runtime recovery, releases, delivery, and P100 controls.

Refreshing a nested `/app/...` route returns the same application shell. The browser never falls back to demo data.

## Bounded local queue

Producer and Admin users see **Local production queue** on Dashboard and Content.

- **Generate more scripts** enqueues between 1 and 20 eligible script jobs.
- **Continue approved locally** initializes only missing audio/visual work for approved scripts and queues MP4 previews only after narration and visuals are approved.
- Brand scope follows the signed-in operator’s assignments.
- The controls never approve, spend, deliver, or publish.

## Browser golden path

### Producer or Admin

1. Open **Create content**.
2. Choose Rawr Nation or Animal X.
3. Write a topic, generate six suggestions, or open an existing approved plan item.
4. Enter the title, objective, audience, platform, format, duration, language, schedule, and optional notes.
5. Select **Create and generate script**.
6. The browser returns immediately with a queued Ollama job.
7. Open the item’s **Production** tab to see queued, running, succeeded, failed, or retried state.
8. When the draft is ready, open **Script** and select **Submit for review**.

### Reviewer

1. Sign in with the Reviewer key.
2. Open **Reviews**.
3. Open the pending script.
4. Review narration sections, factual claims, source evidence, and version status.
5. Enter a specific rationale.
6. Approve the exact version, request changes, or reject it.

### Local media production

1. After script approval, a Producer or Admin opens **Production**.
2. Select **Start local production**.
3. Kokoro narration and ComfyUI keyframes run as background jobs.
4. Generated WAV and image outputs become playable/viewable under **Media review**.
5. Play the available takes and select one passing take for every narration paragraph.
6. Regenerate only a paragraph whose pronunciation, pace, or tone needs correction.
7. Select **Build local mix** after all paragraph takes are selected.
8. Play the authenticated local narration mix and submit it for review.
9. Select one candidate for every scene and submit the visual project.
10. A Reviewer approves narration and visuals.
11. The continuation and preview workers queue and assemble the FFmpeg MP4.
12. Play or export the MP4 from **Media review**.

No model action depends on keeping the browser open. Queue state and attempts survive refresh, sign-out, API restart, and workstation restart.

## Open-source text generation

The local concept and script adapters use:

```text
http://127.0.0.1:11434
```

The default model is configured by `OLLAMA_MODEL` in `.env.local`. The Create Content wizard stores the selected platform, language, duration, objective, audience, and notes in the content brief. The existing validated script service consumes those fields while retaining brand tone, restrictions, claim evidence, deterministic fallback, and exact-version review.

A local-model failure never authorizes paid generation or automatic approval.

## Local narration and alignment

After exact script approval, the P90 service initializes paragraph-bound Kokoro jobs in P87. The aligned local worker:

- claims only approved narration work;
- generates local WAV files with Kokoro;
- runs local `faster-whisper` word recognition;
- anchors the known script to measured word-time evidence;
- requires the configured transcript-coverage threshold;
- validates exact script order and monotonic timing ranges;
- registers canonical internal review assets;
- records zero external cost;
- preserves script and preset lineage;
- leaves final approval blocked until human review.

Default settings:

```env
LOCAL_ALIGNMENT_ENABLED=true
LOCAL_ALIGNMENT_MODEL_ID=tiny
LOCAL_ALIGNMENT_DEVICE=cpu
LOCAL_ALIGNMENT_COMPUTE_TYPE=int8
LOCAL_ALIGNMENT_MINIMUM_COVERAGE=0.72
```

When Whisper is unavailable or coverage/validation fails, the worker records proportional preview timings only. That fallback is playable but cannot satisfy the existing final narration-approval gate. It is never relabeled as forced alignment.

Generated takes and mixes are served only through authenticated, brand-scoped routes and only from `LOCAL_ARTIFACT_ROOT`.

## Local ComfyUI keyframes

The established P68 worker remains the supported GTX 1080 preview runtime.

One-time setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_p68_local_keyframe_worker.ps1 `
  -AcceptModelLicense
```

Then set these values in `.env.local`:

```env
P68_COMFYUI_WORKFLOW_PATH=<absolute path to the reviewed ComfyUI API workflow JSON>
P68_COMFYUI_CHECKPOINT=sd_xl_base_1.0.safetensors
P68_COMFYUI_BASE_URL=http://127.0.0.1:8188
```

Restart the local runtime. Keyframe outputs are internal review assets. Format and corruption checks are automated; creative, continuity, framing, subject, palette, and lighting checks remain human decisions.

## Automated API smoke

After startup, copy the Admin key and run:

```powershell
$env:LOCAL_ADMIN_OPERATOR_KEY = "<admin-key>"
.\.venv\Scripts\python.exe .\scripts\local_golden_path_smoke.py
```

The smoke uses the real API, PostgreSQL, active profiles, local Ollama adapter, workflow, and durable queue. It creates no paid spend, delivery, or publication evidence. Browser acceptance remains the required proof for the full create → review → audio/visual → MP4 flow.

## Remote team access with ngrok

Enable this only after the complete local browser golden path passes.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1 `
  -ExposeWithNgrok
```

Open `http://127.0.0.1:4040` and copy the HTTPS forwarding URL. Team members open that URL and sign in using their own role key.

Security rules:

- never share the Admin key with reviewers;
- do not expose PostgreSQL, Ollama, ComfyUI, artifact, or worker ports;
- expose only the Creator Studio/API port;
- stop ngrok when the review window closes;
- rotate keys when a key is disclosed.

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

The Admin Operations screen exposes canonical candidate discovery, four bounded slots, exactly one external live-result evidence item, controlled draft bootstrap, readiness, and digest-guarded start. Managed slots remain visibly blocked until a supported managed renderer supplies lineage and spend evidence.

Daily local content production does not depend on starting P100.

## What remains intentionally blocked

- Managed natural-motion rendering through Higgsfield or another provider.
- Automatic final approval.
- Automatic social publishing.
- Production rollout before the P100 four-item acceptance pilot passes.
