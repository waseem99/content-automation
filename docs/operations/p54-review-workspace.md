# P54 Local Content Creator Review Workspace

Part of #603. Closes #604–#609 after merge.

## What this builds

P54 creates a local browser-reviewable content creator workspace from one video brief.

It is the first layer intended for a human reviewer to open in a browser and judge whether the generated video pack is usable.

## Inputs

- a local video brief JSON file, or
- a brief object passed from Python

Required brief fields still come from the core pipeline:

- `topic`
- `audience`
- `monetization_goal`

Recommended fields:

- `platform`
- `tone`
- `duration_seconds`
- `must_use_points`
- `avoid`
- `source_notes`

## Outputs

Inside the local project folder:

- `index.html` — browser-openable creator review workspace
- `creator_review.json` — structured review summary and reviewer fields
- `producer_brief.md`
- `script.txt`
- `storyboard.md`
- `shot_list.csv`
- `captions.srt`
- `metadata.json`
- `asset_manifest.json`
- `review_checklist.md`
- `platform_variants.json`
- `manifest.json`
- `summary.json`

## Local command

```bash
python -m src.p54_creator_review_workspace \
  docs/operations/p54-demo-brief.json \
  --output-root outputs/review-demo \
  --project-slug ai-automation-founder-demo \
  --overwrite
```

Then open:

```text
outputs/review-demo/ai-automation-founder-demo-local/index.html
```

## Review purpose

The reviewer can inspect:

- project summary;
- creative hook;
- concept;
- title options;
- script preview;
- storyboard preview;
- shot list preview;
- captions preview;
- rights, engagement, monetization, and production signals;
- next actions;
- artifact links;
- reviewer checklist and decision options.

## Decision options

- `approve_for_production`
- `revise`
- `reject`

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or performance guarantee is introduced.

The workspace is a local static HTML file and local JSON/Markdown/TXT/CSV/SRT artifacts only.
