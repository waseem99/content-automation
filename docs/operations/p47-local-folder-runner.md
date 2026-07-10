# P47 Local CLI and Folder Export Runner

Part of #547. Closes #548–#553 after merge.

## What this builds

P47 turns a brief JSON file into a real local production folder. This is the first step where a producer can run one local command and receive files ready for creative review and video production planning.

## Example local command

```bash
python -m src.p47_local_folder_runner \
  docs/operations/p47-example-brief.json \
  --output-root outputs \
  --overwrite
```

## Expected folder

```text
outputs/ai-automation-for-small-business-owners-youtube-shorts/
  producer_brief.md
  script.txt
  storyboard.md
  shot_list.csv
  captions.srt
  metadata.json
  asset_manifest.json
  review_checklist.md
  platform_variants.json
  manifest.json
  summary.json
```

## Deployment position

This remains local-first. No deployment, API server, rendering, asset download, upload, publishing, external API call, or live platform integration is performed.
