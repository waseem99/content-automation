# P58 One-Command Local Review Cycle Runner

Part of #635. Closes #636–#641 after merge.

## What this builds

P58 provides a single local command that runs the current creator review loop end to end.

It combines:

```text
P55 original demo gallery
→ P56 human feedback and revision queue
→ P57 feedback-driven revised gallery
→ P58 master cycle index and operator report
```

## Default local command

```bash
python -m src.p58_review_cycle_runner \
  --demo-briefs docs/operations/p55-demo-briefs.json \
  --feedback docs/operations/p56-review-feedback-template.json \
  --output-root outputs/review-cycle-demo \
  --overwrite
```

Then open:

```text
outputs/review-cycle-demo/review_cycle_index.html
```

## Inputs

- P55 demo brief library JSON
- P56 reviewer feedback JSON
- local output root

## Outputs

At the review cycle output root:

- `review_cycle_index.html` — master browser-openable local review index
- `review_cycle_summary.json` — machine-readable summary and artifact map
- `operator_run_report.md` — concise operator report
- `original-gallery/index.html` — first-pass generated demo gallery
- `feedback/review_feedback_summary.json`
- `feedback/revision_queue.json`
- `feedback/review_feedback_report.md`
- `regeneration/revised_demo_briefs.json`
- `regeneration/feedback_patch_summary.json`
- `regeneration/feedback_regeneration_report.md`
- `regeneration/revised-gallery/index.html`

## Review flow

1. Open `review_cycle_index.html`.
2. Review the original gallery.
3. Review the feedback report and revision queue.
4. Open the revised gallery.
5. Decide which content packs should move toward production, another revision, or rejection.

## Why this matters

This turns the pipeline into something an operator can actually run and review without manually chaining multiple commands.

It is still local-only. It does not deploy a hosted app and it does not render or publish videos.

## Optional flag

Skip rejected items during regeneration:

```bash
--exclude-rejected
```

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or automated final approval is introduced.

Human approval remains required before production.
