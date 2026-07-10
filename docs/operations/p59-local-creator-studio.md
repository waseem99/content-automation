# P59 Local Creator Studio Starter

Part of #643. Closes #644–#649 after merge.

## What this builds

P59 creates a local, browser-openable Creator Studio starter for drafting video content briefs.

It is not a hosted app. It is a static local HTML file that helps a human create a brief JSON and then run the existing P58 local review cycle.

## Local command

```bash
python -m src.p59_local_creator_studio \
  --output-root outputs/creator-studio \
  --overwrite
```

Then open:

```text
outputs/creator-studio/creator_studio.html
```

## Outputs

At the selected output root:

- `creator_studio.html` — static local brief builder
- `sample_brief.json` — starter video content brief
- `studio_manifest.json` — generated workspace manifest
- `studio_readme.md` — operator instructions

## Workflow

1. Open `creator_studio.html` in a browser.
2. Enter the video topic, platform, audience, tone, duration, monetization goal, required points, avoid points, and source notes.
3. Copy or download the generated JSON.
4. Save it locally as a brief JSON file.
5. Run P58:

```bash
python -m src.p58_review_cycle_runner \
  --demo-briefs path/to/brief.json \
  --feedback docs/operations/p56-review-feedback-template.json \
  --output-root outputs/review-cycle-custom \
  --overwrite
```

Then open:

```text
outputs/review-cycle-custom/review_cycle_index.html
```

## Why this matters

P58 made the review cycle one command. P59 makes brief creation easier for a non-developer by giving them a local form and a sample brief.

## Guardrails

P59 does not:

- deploy a cloud app;
- create a hosted UI/API;
- start an API server;
- render or edit video;
- download assets;
- upload or publish content;
- call external services;
- approve content for production automatically;
- guarantee creative improvement, performance, or monetization.

Human review is required before production.
