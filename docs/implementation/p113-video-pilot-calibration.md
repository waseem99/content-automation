# P113 dual-model video pilot calibration

## Purpose

P113 creates the measured evidence and model-use controls required before P114 installs or runs Wan2.2 and HunyuanVideo 1.5 as production renderers.

It does **not** download model weights, enqueue video generation, approve paid spend, or publish content.

## Model-use policy

The active policy matrix is versioned in `football_brief.video_model_use_policies`.

- `wan-ai / Wan2.2-TI2V-5B` is the default global-public pilot candidate.
- `tencent-hunyuan / HunyuanVideo-1.5-480p-I2V-Step-Distilled` is limited to internal or territory-limited work unless an explicit written-clearance reference is recorded.
- Hunyuan preflight rejects the European Union, United Kingdom and South Korea under the recorded official licence evidence.
- Model policies cannot be edited in place after activation. Evidence or permission changes require a child version.
- The policy matrix supports production governance; it does not replace legal review.

The idempotent onboarding command is:

```powershell
.\.venv\Scripts\python.exe -m src.operations.p113_model_policy_onboarding
```

No access keys are printed or stored in the policy records.

## Pilot structure

A pilot run contains:

1. Three or more complete pilot-video items.
2. Representative clip cases grouped under each item.
3. One or more attempts per case.
4. Separate human review records for succeeded attempts.
5. Versioned report snapshots.

The default plan creates three two-minute pilot groups and six representative shot classes:

- people or animals;
- transition;
- product;
- easy motion;
- map or diagram;
- cinematic hero.

Thirty completed attempts remain the default minimum. Accepted clips are not counted as completed videos unless every non-cancelled case in the pilot item has an accepted output.

## Workstation initialization

After P113 is deployed, initialize the structure from Administrator PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\initialize_p113_pilot.ps1
```

The command:

- captures a point-in-time hardware/software snapshot;
- omits machine names, disk letters, GPU UUIDs, environment variables and credentials;
- seeds the versioned model-use policies;
- creates or resumes the configured pilot run;
- creates three pilot items and six clip cases;
- starts the run;
- remains idempotent when repeated.

It does not start model downloads or generation.

## Measured attempt evidence

Every attempt records immutable generation identity:

- model policy and optional P93 renderer entry;
- optional P87 generation job;
- workflow key and SHA-256;
- checkpoint SHA-256;
- seed;
- width, height, frame count, frame rate and inference steps;
- start and completion timestamps.

Terminal evidence can include:

- wall-clock and GPU-active milliseconds;
- peak VRAM and system RAM;
- average/peak GPU temperature;
- average/peak GPU power;
- output asset;
- external cost;
- failure code and metrics.

A succeeded attempt is reviewed separately for motion quality, reference consistency, artifact control, composition and defect tags.

## API

Authenticated endpoints are under `/video-pilot`:

- model-use matrix and preflight;
- pilot runs;
- complete pilot-video items;
- clip cases;
- attempts and terminal metrics;
- human reviews;
- report preview, snapshot and close.

Admins create and close runs. Production-capable operators can create cases and attempts. Review-capable operators record human decisions.

## Acceptance boundary

P113 remains open until the workstation has produced measured evidence for:

- at least three complete pilot videos;
- at least thirty terminal attempts;
- both local model paths where their distribution policy allows;
- accepted-clip rate and retries;
- GPU and wall-clock timing;
- VRAM, RAM, temperature and power;
- editing and storage observations captured in attempt/report metadata;
- a signed-off global-public, territory-limited and internal model-use matrix.

No theoretical throughput value closes P113.

## Relationship to later work

- P114 consumes P113 policy and measurement records when adding the real ComfyUI video renderer.
- P115 uses accepted motion seconds and retry classes in composition planning.
- P116 uses measured queue throughput to activate cloud workers.
- P117 uses local failure evidence before premium routing.
- P118 uses the pilot report to forecast batches and cost per completed video.
