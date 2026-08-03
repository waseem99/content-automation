# Local GPU Activation — First Canonical MP4

This runbook executes issue #828 under epic #833. It is the only approved path for activating the first real local video workflow.

## Outcome

Convert one approved keyframe into one canonical internal MP4 through the existing PostgreSQL/P87 local-clip queue with:

- exact workflow and checkpoint hashes;
- ComfyUI and custom-node versions;
- prompt, seed, dimensions, frame count, FPS, steps and GPU timing;
- `external_fee_usd = 0`;
- local/Google Drive asset lineage;
- explicit human review;
- no paid-provider call and no public release.

## Hard boundaries

- Use Wan2.2 as the global-public candidate.
- Keep Hunyuan disabled unless territory and licence clearance are recorded.
- ComfyUI must remain loopback-only.
- Register the workflow inactive first.
- Do not activate a guessed or placeholder graph.
- Do not enable automatic paid generation or publishing.
- Generated media, models, credentials and evidence files remain outside Git.

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

## 2. Export the real ComfyUI package

From the workstation graph that actually renders:

1. Export the API-format workflow JSON.
2. Record every checkpoint/model filename used by the graph.
3. Record every required custom-node repository.
4. Do not edit node identifiers after export.
5. Keep ComfyUI at `127.0.0.1`; do not expose port 8188 publicly.

## 3. Collect immutable workstation evidence

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\collect_p114_workstation_evidence.ps1 `
  -ComfyUIRoot "C:\ComfyUI" `
  -WorkflowPath "C:\secure\wan22-ti2v-api.json" `
  -ModelPaths @(
    "C:\ComfyUI\models\diffusion_models\<wan-model-file>",
    "C:\ComfyUI\models\vae\<vae-file>",
    "C:\ComfyUI\models\text_encoders\<encoder-file>"
  ) `
  -OutputPath ".runtime\p114-workstation-evidence.json"
```

Review the JSON before onboarding. Missing files, unresolved Git commits or a non-loopback ComfyUI URL block activation.

## 4. Onboard inactive first

In Creator Studio as Super Admin/Admin:

1. Open **Settings → Renderers**.
2. Add the exact Wan2.2 renderer/model/operation.
3. Attach commercial-use and global-territory evidence.
4. Add the exact workflow JSON SHA-256 and checkpoint SHA-256 values.
5. Keep the workflow and local-video worker inactive.
6. Run preflight against the workstation files.
7. Activate only when every configured hash matches.

Hunyuan remains inactive unless its approved territory covers the intended release destinations.

## 5. Select one proof item

Use one item whose immutable package is already `ready_for_final_video_generation` and whose selected shot has:

- approved keyframe asset;
- rights/source evidence;
- local-motion route;
- supported duration, dimensions and territory;
- no paid reservation.

The first proof should be a simple 3–5 second shot, not a difficult hero sequence.

## 6. Controlled worker activation

1. Enable the dedicated local-video worker for the supervised proof window only.
2. Submit the selected shot through the canonical P87 `local_clip` queue.
3. Keep Creator Studio open for monitoring, but do not depend on the browser remaining open.
4. Confirm only the named job is submitted; never use global ComfyUI interruption.
5. On failure, use bounded retry classes and preserve the failed attempt.

## 7. Required result

The completed attempt must retain:

- P87 job, attempt and provider request identifiers;
- exact input keyframe asset and SHA-256;
- prompt and negative constraints;
- seed, sampler/steps, width, height, FPS and frame count;
- workflow, model and custom-node versions/hashes;
- wall-clock and GPU timing;
- canonical MP4 SHA-256, size and MIME type;
- `external_fee_usd = 0`;
- `internal_only` visibility;
- `review_status = pending` before human review.

## 8. Human review

Review the MP4 for:

- subject and continuity consistency;
- anatomy, faces/hands and object integrity;
- flicker, warping, frozen motion and temporal instability;
- watermarks, unwanted text and compression artifacts;
- framing, camera motion and exact duration;
- rights, territory and model-policy compliance.

Record approve, request changes or reject. Approval does not authorize publishing.

## 9. Close #828 only with evidence

Attach or reference:

- `.runtime/p114-workstation-evidence.json` without secrets;
- exact workflow/checkpoint hashes;
- P87 job and attempt lineage;
- canonical MP4 asset record;
- human review decision;
- confirmation of zero paid-provider calls and zero public releases.

After #828 closes, begin #827 calibration: at least 30 terminal attempts and three completed videos.
