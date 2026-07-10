# P53 Local Before/After QA Comparison and Candidate Selector

Part of #595. Closes #596–#601 after merge.

## What this builds

P53 compares original P50 QA scorecards with revised P52 pilot outputs and produces a local production candidate shortlist.

## Inputs

- original P50 `qa_scorecards.json`
- revised P52 `revised_pilot_index.json`

## Outputs

At the output root:

- `before_after_comparison.json`
- `production_candidate_shortlist.json`
- `revised_qa_scorecards.json`
- `before_after_report.md`

## Local command

```bash
python -m src.p53_before_after_comparator \
  outputs/pilots/qa_scorecards.json \
  outputs/revised-pilots/revised_pilot_index.json \
  --output-root outputs/revised-pilots
```

## Candidate statuses

- `produce_after_human_approval`
- `revise_again`
- `drop_or_rework`

## Deployment position

No deployment, UI/API server, rendering, asset download, upload, publishing, external call, or guaranteed improvement/performance.
