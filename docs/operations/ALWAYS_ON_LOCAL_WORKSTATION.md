# Always-on local content workstation

This runbook turns one supported Windows PC into the local Content Engine host. PostgreSQL, Ollama, Kokoro, ComfyUI keyframes, the Creator Studio API, background workers, and optional ngrok access remain local-first. Human approval is still required for scripts, audio, visual candidates, releases, and delivery.

## Supported production boundary

The GTX 1080 profile supports reviewed SDXL keyframe generation at 704×1280 and the repository's deterministic/Remotion video assembly paths. It is not treated as a supported modern natural-motion video GPU. Higgsfield or another reviewed managed renderer remains the later route for selected natural-motion shots.

## Prerequisites

Install and start:

- Windows 10/11 with the repository on a local NTFS drive;
- Docker Desktop with WSL2 and NVIDIA GPU access;
- current NVIDIA driver;
- Python 3.11 or 3.12 on `PATH`;
- Ollama for Windows;
- Node.js where the existing Remotion/video-engine render path is used;
- ngrok only when remote team access is required.

Configure ngrok outside the repository with your account token. Never place the token in `.env.local`, Git, screenshots, or team messages.

## First deployment

Open **Windows PowerShell as Administrator** in the repository root after pulling `test`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\deploy_always_on_local_production.ps1 `
  -EnableComfyUI `
  -AcceptComfyModelLicense `
  -ExposeWithNgrok
```

Omit `-ExposeWithNgrok` until remote access is needed. The command:

1. creates `.env.local` and four random role-specific operator keys;
2. starts PostgreSQL and applies all migrations;
3. installs Python and Kokoro dependencies;
4. verifies Ollama and pulls the configured open-source model;
5. installs/starts the reviewed GTX 1080 ComfyUI/SDXL preview worker when requested;
6. seeds Rawr Nation, Animal X, roles, profiles, voices, plans, sample content, and local visual presets;
7. installs and starts the `ContentAutomationLocal` Windows scheduled task.

The scheduled task starts after this Windows account signs in. This is intentional because Docker Desktop and Ollama are user-session applications. The supervisor waits for them instead of failing during boot.

## Access

- Local Creator Studio: `http://127.0.0.1:8000/`
- Role keys: `.runtime\operator-keys.json`
- Supervisor heartbeat: `.runtime\supervisor-heartbeat.json`
- Logs: `.runtime\logs\`
- ngrok local inspector: `http://127.0.0.1:4040`

Share only the HTTPS ngrok forwarding URL and the correct role key with a team member. Do not share the Admin key unless the person is actually an administrator.

## Always-on behavior

The scheduled task restarts the supervisor if it exits. The supervisor independently restarts:

- the FastAPI/Creator Studio process;
- the script and narration worker;
- the ComfyUI visual worker;
- ngrok, when enabled.

Restart delay increases after repeated crashes and resets after a stable period. The API is also force-restarted if it remains alive but unready. PostgreSQL uses Docker's `unless-stopped` policy. Queue leases and stale-job recovery preserve queued work after process or PC restarts.

## Production queue

A Producer uses **Generate more scripts** to enqueue a bounded batch of 1–20 eligible script drafts. The button never creates an infinite generator and never bypasses concept approval.

The text/audio worker processes queued Ollama script jobs and Kokoro narration jobs. After a Reviewer explicitly approves a script, background workers periodically initialize missing local audio and ComfyUI visual-candidate work. All results remain pending human review.

The **Continue approved locally** button triggers the same approved-only continuation immediately.

## Status and recovery

```powershell
Get-ScheduledTask -TaskName ContentAutomationLocal
Get-Content .\.runtime\supervisor-heartbeat.json -Raw
Get-Content .\.runtime\logs\supervisor.log -Tail 100
Get-Content .\.runtime\logs\api.error.log -Tail 100
Get-Content .\.runtime\logs\text-audio-worker.error.log -Tail 100
Get-Content .\.runtime\logs\visual-worker.error.log -Tail 100
```

Force a safe restart:

```powershell
Stop-ScheduledTask -TaskName ContentAutomationLocal
Start-ScheduledTask -TaskName ContentAutomationLocal
```

The database, models, artifacts, and queued jobs are preserved.

## Stop or remove auto-start

Stop but keep the scheduled task installed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_always_on_local_production.ps1 -KeepTask
```

Stop and uninstall the task:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_always_on_local_production.ps1
```

No stop command deletes PostgreSQL data, models, generated artifacts, or queue records.

## Safety controls

This workstation configuration does not enable:

- automatic approval;
- automatic publication;
- paid generation;
- Higgsfield or another managed renderer;
- browser automation;
- Vercel media processing;
- storage of operator keys or ngrok credentials in Git.
