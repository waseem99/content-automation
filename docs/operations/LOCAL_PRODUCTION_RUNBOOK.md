# Local Production Runtime

This runbook starts the multi-brand Creator Studio, PostgreSQL, operator API, local queue worker, Ollama concept/script generation, and Kokoro narration on one Windows workstation. ComfyUI keyframes are optional and remain loopback-only.

## Boundaries

- Local generation is the default.
- Every concept, script, narration, image, route, release, and delivery decision remains human-controlled.
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
4. Creates `.venv` and installs application and Kokoro dependencies.
5. verifies Ollama and pulls the configured open-source model.
6. Applies all PostgreSQL migrations through `0090`.
7. Idempotently seeds Rawr Nation, Animal X, roles, brand assignments, profiles, narration presets, draft plans, and one safe smoke content item per brand.
8. Starts the FastAPI/Creator Studio at `http://127.0.0.1:8000`.
9. Starts the P87 local queue worker for Kokoro narration and ComfyUI keyframes.

Operator keys are written to:

```text
.runtime/operator-keys.json
```

Share only the key matching the team member’s role.

## Open-source text generation

The local concept and script adapters use the Ollama-compatible endpoint:

```text
http://127.0.0.1:11434
```

The default model is configured by `OLLAMA_MODEL` in `.env.local`. The adapters record the model, seed, and whether deterministic fallback was used. A local-model failure never authorizes paid generation or automatic approval.

## Local narration queue

When an approved script enters audio production, the existing P90 service enqueues paragraph-bound Kokoro jobs in P87. The local worker:

- claims only narration and keyframe jobs;
- generates local WAV files with Kokoro;
- registers a canonical internal-only asset;
- records zero external cost;
- registers proportional preview timing;
- leaves final approval blocked until human review and final alignment requirements are satisfied.

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

Restart the local runtime. Keyframe outputs are registered as internal review assets. Format and corruption checks are automated; creative, continuity, framing, subject, palette, and lighting checks remain pending human review.

## Golden-path smoke

After startup, copy the admin key from `.runtime/operator-keys.json` and run:

```powershell
$env:LOCAL_ADMIN_OPERATOR_KEY = "<admin-key>"
.\.venv\Scripts\python.exe .\scripts\local_golden_path_smoke.py
```

The smoke uses the real API, PostgreSQL database, active brand profile, local Ollama adapter, production workflow, and P87 queue. It creates no approval, spend, delivery, or publication evidence. Its expected stop is the first human concept-review gate.

After the reviewer shortlists and approves the concept in Creator Studio, continue with script generation and review. Approved scripts can then initialize Kokoro narration and ComfyUI visual candidates, which the queue worker processes.

## Remote team access with ngrok

Start with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1 `
  -ExposeWithNgrok
```

Open the local ngrok inspector at `http://127.0.0.1:4040` and copy the HTTPS forwarding URL. Team members open that URL and sign in using their own operator key.

Security rules:

- never share the Admin key with reviewers;
- do not expose PostgreSQL, Ollama, ComfyUI, or worker ports;
- expose only the Creator Studio/API port;
- stop ngrok when the review window closes;
- rotate keys by regenerating `.env.local` and rerunning onboarding if a key is disclosed.

## Logs and recovery

```text
.runtime/logs/api.log
.runtime/logs/api.error.log
.runtime/logs/worker.log
.runtime/logs/worker.error.log
```

Queued jobs use leases, retries, stale-worker recovery, and immutable attempts. Restarting the API or worker does not erase PostgreSQL, models, or artifacts.

Stop services while preserving data:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\stop_local_production.ps1
```

Stop API/worker/ngrok while leaving PostgreSQL running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\stop_local_production.ps1 `
  -KeepDatabase
```

## What remains intentionally blocked

- Managed natural-motion rendering through Higgsfield or another provider.
- Automatic final approval.
- Automatic social publishing.
- Production rollout before the P100 four-item acceptance pilot passes.
