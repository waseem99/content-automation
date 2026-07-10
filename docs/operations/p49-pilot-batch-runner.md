# P49 Real Pilot Content Batch Runner

Part of #563. Closes #564–#569 after merge.

## What this builds

P49 moves from generic capability to real local pilot review. It runs multiple realistic video briefs through the local workflow and creates production folders for human creative review.

## Local command

```bash
python -m src.p49_pilot_batch_runner \
  docs/operations/p49-pilot-briefs.json \
  --output-root outputs/pilots \
  --overwrite
```

## Output

At the batch root:

- `pilot_index.json`
- `pilot_review_checklist.md`

Inside each pilot folder:

- P47 producer/export files
- `platform_templates.json`

## Why this matters

This lets the team review real script/storyboard/platform outputs before spending on UI, API, deployment, video rendering, or upload automation.

## Deployment position

No cloud deployment, UI/API server, trend scraping, rendering, asset download, upload, publishing, platform API call, or performance guarantee.
