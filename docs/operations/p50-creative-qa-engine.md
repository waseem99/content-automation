# P50 Local Creative QA and Pilot Scoring Engine

Part of #571. Closes #572–#577 after merge.

## What this builds

P50 adds a local creative QA layer for pilot batches before production, rendering, UI/API, or deployment work.

## Inputs

- P49 batch result, or
- local `pilot_index.json`

## Outputs

At the batch root:

- `qa_scorecards.json`
- `qa_summary.md`
- `qa_scorecards/<pilot>.md`

## QA dimensions

- hook strength
- clarity
- retention potential
- platform fit
- originality
- rights readiness
- monetization fit
- production feasibility

## Decision

Each pilot receives an accept/revise/block-style recommendation. The batch receives a final QA decision.

## Deployment position

No deployment, UI/API server, rendering, asset download, upload, publishing, external call, or performance guarantee.
