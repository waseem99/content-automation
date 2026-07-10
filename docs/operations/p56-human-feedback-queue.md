# P56 Local Human Feedback and Revision Queue

Part of #619. Closes #620–#625 after merge.

## What this builds

P56 converts human review decisions from the P55 demo gallery into a structured local feedback report and prioritized revision queue.

This is the next practical step after the local demo gallery: instead of simply looking at generated content, reviewers can mark each demo as approved, needs revision, or rejected, then generate actionable local outputs.

## Inputs

- P55 `demo_gallery.json`
- reviewer feedback JSON, such as `docs/operations/p56-review-feedback-template.json`

Reviewer feedback supports:

- `demo_slug`
- `decision`: `approve_for_production`, `revise`, or `reject`
- `score`: 0–100
- `strengths`
- `issues`
- `requested_changes`
- `approval_notes`

## Outputs

At the selected output root:

- `review_feedback_summary.json`
- `revision_queue.json`
- `review_feedback_report.md`

## Local command

```bash
python -m src.p56_human_feedback_queue \
  outputs/demo-gallery/demo_gallery.json \
  docs/operations/p56-review-feedback-template.json \
  --output-root outputs/demo-gallery
```

## Review loop

```text
generate demo gallery
→ open gallery in browser
→ review each demo workspace
→ fill reviewer feedback JSON
→ generate feedback report and revision queue
→ revise weak demos in the next local pass
```

## Decision meaning

- `approve_for_production`: strong enough to move toward production after final human approval.
- `revise`: potentially useful but needs creative, rights, or editor-handoff improvements.
- `reject`: not worth producing in its current form; rework or discard.

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or automated final approval is introduced.

The output is local JSON and Markdown only.
