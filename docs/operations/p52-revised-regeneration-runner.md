# P52 Local Revised Pilot Regeneration Runner

Part of #587. Closes #588–#593 after merge.

## What this builds

P52 applies P51 revision patches to the original P49 pilot briefs and runs a second local generation pass.

## Inputs

- original pilot brief library, such as `docs/operations/p49-pilot-briefs.json`
- P51 `revision_plan.json`

## Outputs

At the revised output root:

- `revised_pilot_briefs.json`
- `revised_pilot_index.json`
- `revised_generation_summary.md`
- one revised local production folder per pilot
- `platform_templates.json` inside each revised pilot folder

## Local command

```bash
python -m src.p52_revised_regeneration_runner \
  docs/operations/p49-pilot-briefs.json \
  outputs/pilots/revision_plan.json \
  --output-root outputs/revised-pilots \
  --overwrite
```

## Why this matters

This creates a low-cost local iteration loop:

```text
pilot briefs → first generation → QA → revision plan → revised generation → human comparison
```

## Deployment position

No deployment, UI/API server, rendering, asset download, upload, publishing, external call, or guaranteed improvement.
