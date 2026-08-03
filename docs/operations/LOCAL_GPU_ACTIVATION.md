# Local GPU Activation — First Canonical MP4

This runbook executes issue #828 under epic #833. It is the approved path for activating the first real local video workflow.

## Required outcome

Convert one approved keyframe into one canonical internal MP4 through the PostgreSQL/P87 `local_clip` queue with:

- exact workflow, model and checkpoint hashes;
- ComfyUI and custom-node versions;
- prompt, seed, dimensions, FPS, frame count and steps;
- wall-clock and GPU timing;
- canonical MP4 SHA-256, size and MIME type;
- `external_fee_usd = 0`;
- `internal_only` lifecycle and pending human review;
- no paid-provider call and no public release.

## Hard boundaries

- Wan2.2 is the global-public local candidate.
- Hunyuan stays disabled unless territory and licence clearance are recorded.
- ComfyUI remains loopback-only.
- PostgreSQL remains the only workflow/status system of record.
- Generated files remain local or in registered Google Drive locations.
- Never activate a guessed workflow or placeholder checkpoint.
- Automatic paid generation, final approval and public publishing remain disabled.

## 1. Update and preserve the workstation

```powershell
git status
git checkout test
git pull --ff-only origin test
```

Preserve:

```text
.env.local
.runtime/artifacts
.runtime/operator-keys.json
PostgreSQL/Docker volumes
Ollama models
ComfyUI models and custom nodes
```

Start the platform and pass readiness:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\start_local_production.ps1

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\check_production_readiness.ps1
```

## 2. Prepare the real ComfyUI package

Use the workstation graph that actually renders:

1. Export API-format workflow JSON.
2. Record every checkpoint/model filename.
3. Record required custom-node repositories and commits.
4. Keep ComfyUI on `127.0.0.1:8188`.
5. Do not edit node identifiers after export.

The repository manifest and API workflow must match the actual workstation files exactly.

## 3. Select the proof item

Use a simple 3–5 second local-motion shot whose immutable package is `ready_for_final_video_generation` and has:

- an approved selected keyframe;
- source and rights evidence;
- supported duration, resolution and territory;
- no paid reservation.

## 4. Run the supervised proof

The command below performs GPU validation, workstation evidence collection, live ComfyUI node/input schema validation, canonical activation, one P87 → P114 render and strict MP4 evidence verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\prove_p114_first_local_mp4.ps1 `
  -ComfyUIRoot "D:\ComfyUI\App"
```

It requires a 24 GB-class GPU by default. The threshold may be changed only for a separately approved hardware experiment.

Optional prompt validation with a known approved keyframe:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\prove_p114_first_local_mp4.ps1 `
  -ComfyUIRoot "D:\ComfyUI\App" `
  -ProbePrompt `
  -DiagnosticInputImage "C:\secure\approved-keyframe.png"
```

Prompt probing is opt-in because a valid `/prompt` request may begin execution before queue deletion. The normal proof itself uses the canonical P87 worker path.

## 5. Diagnostic evidence

Evidence is written under:

```text
.runtime/p114-first-local-mp4/
.runtime/p114-readiness.json
.runtime/logs/p114-activation/
```

The live-schema diagnostic reports:

- missing node classes;
- missing required inputs;
- unknown inputs;
- invalid literal option values;
- workflow/manifest SHA mismatch;
- queue state.

The canonical worker preserves the complete ComfyUI JSON/text rejection body when `/prompt` returns HTTP 400 instead of recording only a generic status message.

Do not disable workflow, model, licence, territory or hash validation to make the proof pass.

## 6. Required database and file evidence

The proof command fails unless the latest local-video execution has:

- succeeded job, attempt and execution states;
- provider request ID;
- canonical output asset ID;
- real `.mp4` file and `video/mp4` MIME type;
- matching database/file size and SHA-256;
- zero job and execution cost;
- `internal_only` lifecycle;
- `review_status = pending`;
- human review required;
- automatic approval and publishing disabled.

## 7. Human review

Review the MP4 for:

- subject and continuity consistency;
- anatomy, faces/hands and object integrity;
- flicker, warping, frozen motion and temporal instability;
- unwanted text, watermarks and compression artifacts;
- framing, camera motion and duration;
- rights, territory and model-policy compliance.

Record approve, request changes or reject. Approval does not authorize publishing.

## 8. Close #828 only with evidence

Reference:

- workstation and GPU evidence;
- exact workflow/checkpoint/custom-node hashes;
- P87 job and attempt lineage;
- canonical MP4 asset record;
- human review decision;
- confirmation of zero paid-provider calls and zero public releases.

After #828 closes, begin #827 calibration: at least 30 terminal attempts and three completed pilot videos with accepted seconds/GPU hour, retries, VRAM, temperature, storage, edit time and cost/video.
