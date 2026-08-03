# Automated Platform Acceptance

This runbook validates Creator Studio through a real Playwright-controlled browser while PostgreSQL remains the workflow system of record. Normal acceptance is no-cost: provider execution and public publishing must be disabled before the runner starts.

## What the suite proves

The suite covers:

- local and optional ngrok readiness;
- database, schema and migration readiness;
- invalid-key rejection and three-role access boundaries;
- dashboard, campaigns, content, reviews, team, settings and operations navigation;
- one isolated database-native QA campaign through create, validate, activate, autopilot, pause and resume;
- UI/API reconciliation for campaign dashboard, item grid and grouped exceptions;
- browser console, page error and unexpected 5xx collection;
- recovery from a temporary API failure;
- session persistence across refresh;
- serious/critical axe accessibility checks;
- laptop and desktop viewport checks;
- unauthenticated API rejection;
- no browser request to fal, Vidu or YouTube upload origins;
- remote Creator Studio authentication boundary;
- optional cross-browser smoke coverage;
- a separate fail-closed live-provider reservation gate.

Passing the suite does not mean theoretical certainty. Release confidence requires three consecutive full no-cost passes, zero P0/P1 findings, and one separately approved provider-generated clip with canonical lineage and human review.

## Safety preflight

`run_platform_acceptance.ps1` refuses to start unless all of these are disabled in `.env.local`:

```text
PROVIDER_PAID_EXECUTION_ENABLED=false
HYBRID_PAID_EXECUTION_ENABLED=false
HYBRID_PUBLIC_PUBLISHING_ENABLED=false
```

The runner reads operator keys only into the child process environment and removes them afterward. Keys are not written to reports. Mutating runs take a PostgreSQL custom-format backup first unless explicitly skipped.

## Install once

Run PowerShell from the repository root:

```powershell
& .\scripts\windows\install_platform_acceptance.ps1
```

For Chromium, Firefox and WebKit:

```powershell
& .\scripts\windows\install_platform_acceptance.ps1 -InstallAllBrowsers
```

Node.js 20 or newer is required. The repository pins Playwright Test and axe integration versions in `package.json`.

## Fast deployment smoke

```powershell
& .\scripts\windows\run_platform_smoke.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -RemoteUrl "https://YOUR-NGROK-DOMAIN" `
  -Headed `
  -OpenReport
```

The browser is isolated from the user's normal Chrome or Opera profile.

## Full no-cost acceptance

```powershell
& .\scripts\windows\run_platform_acceptance.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -RemoteUrl "https://YOUR-NGROK-DOMAIN" `
  -Headed `
  -Mutating `
  -OpenReport
```

`-Mutating` creates one permanent audit-labelled QA campaign. It does not render final video, call a paid provider or publish content. Immutable QA records remain tagged with the run ID.

Add `-CrossBrowser` for Chromium, Firefox and WebKit. Cross-browser runs take longer and should follow a clean Chromium run.

## Evidence

Each run is retained under:

```text
.runtime/e2e/platform-<UTC timestamp>/
```

The `latest` junction points to the most recent run. Evidence includes:

- `run-metadata.json`;
- `summary.md` and `summary.json`;
- `defects.md`;
- `improvements.md`;
- `results.json`;
- `junit.xml`;
- HTML report;
- failure traces, screenshots and videos;
- pre-run PostgreSQL backup for mutating runs.

Open a trace with:

```powershell
npx playwright show-trace <trace.zip>
```

## Severity and closure

- **P0** — security, data loss, unintended spend or unintended publishing;
- **P1** — critical journey cannot complete;
- **P2** — important reliability, evidence, accessibility or usability defect;
- **P3** — minor UX or presentation defect.

Do not proceed to provider calibration while any P0/P1 finding remains. Keep P2/P3 findings in the acceptance report and convert them into repository issues or a focused defect-fix PR.

## Controlled live-provider acceptance

The live-provider runner is intentionally separate. It does not create a routing plan or approve spending. It accepts only an existing, reviewed and approved plan plus a reservation payload.

Example for a maximum USD 0.15 fal request:

```powershell
& .\scripts\windows\run_live_provider_acceptance.ps1 `
  -Provider fal `
  -RoutingPlanId "<approved-plan-uuid>" `
  -ReservationPayloadFile "C:\secure\first-fal-reservation.json" `
  -MaximumSpendUsd 0.15 `
  -Confirmation "SPEND-FAL-0.15"
```

The payload file must contain the already-approved routing item, for example:

```json
{
  "routing_item_id": "<approved-routing-item-uuid>",
  "priority": 100,
  "timeout_seconds": 1800,
  "max_attempts": 1
}
```

The runner verifies the plan, approved ceiling, explicit confirmation and maximum amount, then reserves and enqueues exactly one managed job. The provider worker still owns submission, request-ID recovery, output download and canonical asset registration. Human creative review remains required.

## Current expected improvement finding

The release-readiness test deliberately fails when `/runtime/ready` reports an all-zero Git SHA or configuration digest. Fix deployment evidence before using a clean acceptance report as production sign-off.
