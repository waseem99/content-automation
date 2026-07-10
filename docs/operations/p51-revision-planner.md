# P51 Local Pilot Revision Planner

Part of #579. Closes #580–#585 after merge.

## What this builds

P51 converts P50 creative QA findings into concrete revision packs. This creates the bridge from “we scored the pilots” to “we know exactly what to change before regenerating or producing them.”

## Inputs

- P50 QA pack, or
- local `qa_scorecards.json`

## Outputs

At the revision output root:

- `revision_plan.json`
- `revision_summary.md`
- `revision_packs/<pilot>.md`
- `revised_brief_patches/<pilot>.json`

## Local command

```bash
python -m src.p51_revision_planner \
  outputs/pilots/qa_scorecards.json \
  --output-root outputs/pilots
```

## Revision dimensions

- hook strength
- clarity
- retention potential
- platform fit
- originality
- rights readiness
- monetization fit
- production feasibility

## Deployment position

No deployment, UI/API server, rendering, asset download, upload, publishing, external call, or automated production decision. Human approval remains required.
