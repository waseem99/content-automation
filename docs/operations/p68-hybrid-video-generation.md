# P68 hybrid video generation

This runbook turns the P68 still-based technical previews into reviewable videos with genuine shot motion while preserving cost, continuity, provenance, and publication gates.

## Current scope

The two gold pilots use three complementary visual paths:

| Shot type | Development path | Production path |
|---|---|---|
| Factual mechanism or test | Deterministic, code-authored animation | Keep when editorial and factual review approve it |
| Natural subject behavior | Wan 2.2 TI2V-5B on the private RN ComfyUI worker | Keep when it passes; escalate only a failed shot to an approved premium provider |
| Voice, captions, and finishing | Local Kokoro narration plus FFmpeg assembly | Retain or selectively upgrade voice/music after human review |

The existing hybrid reviews are not production candidates. Rawr has authored motion for S02–S06 and still needs a generated S01 hook. Animal X has authored motion for S03–S04 and still needs generated S01, S02, S05, and S06 behavior shots. S01 in both pilots may start from its explicitly designated continuity master. Animal X S02, S05, and S06 remain blocked until purpose-built keyframes exist.

## Safety and monetization boundaries

- Generated media, ledgers, and review renders stay outside Git.
- Every job records the input hash, prompt hash, seed, model, provider job ID, output hash, cost, and terms evidence.
- Raw ComfyUI binds to loopback by default. Use SSH forwarding or an authenticated TLS proxy for remote access.
- Development output remains `publish_allowed: false` while model checksums or the terms snapshot are pending.
- A self-hosted job reserves its estimated GPU cost before submission. The default soft cap is USD 4 and hard cap is USD 10 per pilot.
- Any premium-provider path is treated as `needs_approval` even below the soft cap. No paid call is automatic.
- Reference videos may inform abstract pacing and storytelling only; source frames, voices, music, branding, and shot-for-shot expression do not enter the output.

## Deploy the RN worker

On the GPU-capable RN host:

```bash
cd deploy/p68-rn-worker
cp .env.example .env
# Set reviewed COMFYUI_REF, WAN22_REVISION, and WAN21_REVISION commit SHAs,
# plus absolute model/input/output paths.
source .env
./download-models.sh "$RN_MODEL_DIR" "$WAN22_REVISION" "$WAN21_REVISION"
docker compose build
docker compose up -d
curl --fail "http://127.0.0.1:${RN_COMFYUI_PORT}/system_stats"
```

Before treating output as commercially reviewable, copy the downloaded SHA-256 values into `model-manifest.json`, capture a SHA-256 snapshot of the applicable model license/terms, review commercial-use and modification permissions, and change the evidence status through a reviewed repository change. Do not expose port 8188 publicly.

In the application environment set:

```bash
P68_RN_BASE_URL=http://127.0.0.1:8188
P68_RN_GPU_HOURLY_USD=<actual RN hourly cost>
P68_VIDEO_SOFT_CAP_USD=4.00
P68_VIDEO_HARD_CAP_USD=10.00
```

## Generate in short, resumable commands

These commands return quickly; generation continues on RN, avoiding a long client request that can time out.

```bash
PYTHONPATH=. python scripts/p68_generate_clips.py health

PYTHONPATH=. python scripts/p68_generate_clips.py submit \
  --pilot rawr-blind-spot --shots S01

PYTHONPATH=. python scripts/p68_generate_clips.py submit \
  --pilot animal-elephant-signals --shots S01

PYTHONPATH=. python scripts/p68_generate_clips.py status --pilot rawr-blind-spot
PYTHONPATH=. python scripts/p68_generate_clips.py refresh --pilot rawr-blind-spot
```

The default is one variant for a standard shot and two variants for a hook or reveal. `submit` is idempotent; repeating it does not intentionally resubmit a recorded request. Use `refresh` periodically until candidates are downloaded.

After purpose-built Animal X keyframes named `s02-*.png`, `s05-*.png`, and `s06-*.png` are present, refresh its asset manifest and submit those shots. The generator refuses an undesignated generic master by default.

## Select and assemble

Review the generated candidates and select one variant per generated shot:

```bash
PYTHONPATH=. python scripts/p68_select_clips.py \
  --pilot rawr-blind-spot --select S01=2 \
  --reviewer "editor-name" --note "Best immediate motion and stable anatomy"

PYTHONPATH=. python scripts/p68_build_hybrid_reviews.py --pilot rawr-blind-spot
```

Selection approves a clip only for the next review assembly. It does not approve factual accuracy, rights, originality, advertiser suitability, final creative quality, monetization, or publication.

## Quality decision and paid escalation

Review each shot for immediate motion, anatomy/identity stability, credible behavior, camera intent, continuity at both cut points, factual clarity, caption safe zones, and narration fit. Also review the complete story for hook strength, visual resets, payoff clarity, pacing, and audio continuity.

Use a premium provider only when all of the following are true:

1. the shot is important to hook, reveal, or comprehension;
2. at least two RN variants fail a documented quality dimension;
3. prompt or keyframe correction is unlikely to fix the failure cheaply;
4. commercial terms and output rights have been captured;
5. an operator approves the provider, shot, maximum attempt count, and cost ceiling.

Escalate only that shot, normally for one or two variants. Feed the result through the same candidate manifest, digest verification, operator selection, stitching, and review gates. Keep RN output for every shot that already passes; a premium tool is not a reason to regenerate the whole video.

## Completion criteria

A pilot may be called a production candidate only after there are no still-master fallbacks, every selected clip has an approved provenance record, the automated media checks pass, and the 12-dimension human benchmark review records no hard-gate failure. Publication remains a separate decision.
