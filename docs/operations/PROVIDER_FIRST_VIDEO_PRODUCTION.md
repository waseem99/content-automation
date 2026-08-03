# Provider-First Video Production

This runbook activates real final-video generation without requiring a 24 GB local GPU. Creator Studio and PostgreSQL remain the control plane; official managed APIs perform only the approved GPU-heavy clip generation.

## Locked production model

```text
approved campaign item
→ immutable ready-for-final-video-generation package
→ renderer preflight and exact quote
→ human spend decision
→ reserved P87 premium_clip job
→ fal or Vidu official API worker
→ immediate output download and SHA-256 registration
→ internal-only shared artifact pending human review
→ deterministic composition and final QA
→ explicit release or publishing action
```

The first provider preference is:

1. `fal` with `fal-ai/wan/v2.2-5b/image-to-video` for standard image-to-video motion.
2. `vidu` for secondary production, longer clips, references and difficult motion.
3. Existing Higgsfield integration for approved specialist use.
4. Veo or another premium hero route only after a separate catalogue, terms and budget review.

Local ComfyUI remains optional future cost optimization. It is not a production dependency.

## Safety boundaries

- Provider credentials are stored in Windows user environment variables, never Git or PostgreSQL.
- Setup does not submit a generation or spend credits.
- Workers cannot start unless `PROVIDER_PAID_EXECUTION_ENABLED=true`.
- A worker can claim only an already-approved P94 managed route with a spend reservation.
- Every provider request ID is written to the generation attempt before polling.
- Restarted workers reuse the existing provider request ID and do not duplicate paid submissions.
- Provider outputs are downloaded immediately, hashed and registered as `internal_only`.
- Every output remains `review_status=pending` and requires human creative review.
- Automatic spend approval, creative approval and public publishing remain disabled.

## Accounts and evidence required

For each provider, retain:

- company-controlled account;
- official API key;
- current reviewed pricing;
- official usage/commercial terms URL;
- a dated local evidence file containing the reviewed pricing and terms decision;
- approved maximum monthly and per-content budgets.

Do not send API keys through WhatsApp, Creator Studio or GitHub.

## Configure providers

Keep Creator Studio and PostgreSQL running. Open PowerShell as Administrator from the repository root.

Example for both providers:

```powershell
& .\scripts\windows\setup_provider_first_rendering.ps1 `
  -Provider both `
  -FalPricePerSecondUsd <reviewed-fal-price> `
  -FalUsageTermsUrl "<official-fal-terms-url>" `
  -FalUsageEvidenceFile "C:\secure\fal-terms-and-pricing.txt" `
  -ViduPricePerSecondUsd <reviewed-vidu-price> `
  -ViduUsdPerCredit <reviewed-credit-value-if-known> `
  -ViduUsageTermsUrl "<official-vidu-terms-url>" `
  -ViduUsageEvidenceFile "C:\secure\vidu-terms-and-pricing.txt"
```

The script prompts for API keys with hidden input and stores them as Windows user environment variables. It creates versioned P93 renderer entries, records terms digests, marks them degraded until the first real validation, and creates no-spend provider worker identities.

## Explicitly enable paid execution

Only after budgets and the first shot are approved:

```powershell
& .\scripts\windows\setup_provider_first_rendering.ps1 `
  -Provider both `
  -FalPricePerSecondUsd <reviewed-fal-price> `
  -FalUsageTermsUrl "<official-fal-terms-url>" `
  -FalUsageEvidenceFile "C:\secure\fal-terms-and-pricing.txt" `
  -ViduPricePerSecondUsd <reviewed-vidu-price> `
  -ViduUsdPerCredit <reviewed-credit-value-if-known> `
  -ViduUsageTermsUrl "<official-vidu-terms-url>" `
  -ViduUsageEvidenceFile "C:\secure\vidu-terms-and-pricing.txt" `
  -EnablePaidExecution `
  -InstallAlwaysOnWorkers
```

This enables workers. It still does not create a provider request. Requests begin only after an Admin/Reviewer completes the existing preflight, routing-plan, spend-decision and reservation flow.

## First canonical provider MP4

Use one approved 3–5 second image-to-video shot.

Required retained evidence:

- provider and model;
- renderer catalogue entry and preflight;
- approved routing plan and spend ceiling;
- spend reservation and P87 job/attempt IDs;
- reviewed keyframe asset ID;
- exact prompt, duration, resolution, FPS and optional seed;
- provider request ID;
- provider response digest and credits/cost;
- downloaded video MIME type, size and SHA-256;
- canonical asset and shared-artifact IDs;
- `internal_only` lifecycle;
- pending human review;
- no automatic publishing.

The first real provider-generated MP4 is not proven until a human records approve, changes requested or reject.

## Pilot and calibration

After the first MP4, run at least 30 representative attempts and complete three pilot videos. Measure:

- accepted clips and accepted seconds;
- attempts per accepted clip;
- provider latency and availability;
- generated, retried and accepted paid seconds;
- credits and USD cost;
- cost per accepted second and per completed video;
- faces/hands, product consistency, continuity, flicker, warping and text artifacts;
- review and editing time.

Start with a six-video creative pilot, then a 20-video batch, then 40–50-video batches. Do not forecast 300-video throughput before measured evidence exists.

## Operations

Provider status:

```powershell
Get-Content .\.runtime\provider-workers-heartbeat.json -Raw
```

Provider logs:

```powershell
Get-Content .\.runtime\logs\fal-worker.error.log -Tail 100
Get-Content .\.runtime\logs\vidu-worker.error.log -Tail 100
```

Stop workers without deleting jobs or evidence:

```powershell
& .\scripts\windows\stop_provider_workers.ps1
```

The ngrok URL exposes only Creator Studio/API. Provider credentials, workers, PostgreSQL and artifacts remain private on the host.
