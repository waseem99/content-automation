# Official Higgsfield managed renderer

Content Automation integrates Higgsfield only through the official `@higgsfield/cli` account flow. Browser cookies, private endpoints, desktop macros and copied provider sessions are prohibited.

## What the integration does

- authenticates the approved Higgsfield account through the official browser login;
- verifies one exact model through the official CLI;
- creates an active renderer catalogue entry with reviewed pricing and terms evidence;
- starts an isolated supervised worker with no operator API key;
- claims only approved P87 `premium_clip` jobs for provider `higgsfield`;
- reuses an existing provider generation ID after a worker restart to prevent duplicate spend;
- polls through the official CLI and downloads the completed output;
- records actual cost when provided, otherwise conservatively records the approved reservation/estimate ceiling;
- ingests the clip into the canonical local shared artifact store;
- leaves the clip at pending human review;
- never approves content, authorizes spend, assembles a release or publishes.

## Account and catalogue setup

Prepare a local file containing reviewed commercial-use and pricing/terms evidence. Keep the file outside Git. Then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\windows\setup_higgsfield_official.ps1 `
  -ModelKey "<official-model-key>" `
  -ModelDisplayName "<human-readable-model-name>" `
  -PricePerSecondUsd 0.50 `
  -UsageTermsUrl "https://<official-terms-url>" `
  -UsageEvidenceFile "C:\secure\higgsfield-terms-evidence.txt" `
  -Width 720 `
  -Height 1280 `
  -MinDurationSeconds 1 `
  -MaxDurationSeconds 10 `
  -InstallSkills
```

Use the exact price shown by the approved Higgsfield account/model. The example price above is not a quotation.

The setup command performs no generation and incurs no credit spend. It enables the worker only after account authentication, model verification, pricing and terms evidence are recorded.

## First managed-shot proof

1. Create and approve the local visual candidate and prompt.
2. Create a managed route against the active Higgsfield catalogue entry.
3. Review the preflight quote.
4. Have an Admin independently approve a hard spend ceiling.
5. Enqueue one managed shot only.
6. Confirm the Higgsfield worker claims the job and records a provider generation ID.
7. Confirm the completed output is downloaded into `.runtime/artifacts` and registered as a shared `premium_clip` artifact.
8. Review continuity, anatomy, watermarking, framing, motion, rights and technical media quality.
9. Approve or reject the exact artifact version.
10. Confirm actual cost and spend-reservation reconciliation.

Do not enable a whole-video managed render. Escalate only approved shots that could not meet quality requirements locally.

## Recovery

When the worker restarts after submission, it reads the existing `provider_request_id` from the current generation attempt and polls that job rather than submitting a second request.

If authentication is revoked or the model disappears:

- the worker fails closed;
- the job retains provider/request/cost/error evidence;
- no automatic fallback provider is invoked;
- the Admin may correct the account/catalogue and explicitly retry the job.

## Acceptance boundary

Repository and CI completion do not close issue #797. The issue closes only after one real credit-consuming output has complete quote, approval, provider/model/request lineage, canonical artifact checksum, cost reconciliation and human quality review evidence.
