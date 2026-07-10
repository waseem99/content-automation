# P57 Local Feedback-Driven Regeneration Gallery

Part of #627. Closes #628–#633 after merge.

## What this builds

P57 turns P56 human review feedback into a revised local demo brief library and a new local demo gallery.

This creates a practical loop:

```text
generate demo gallery
→ human reviews outputs
→ build revision queue
→ regenerate revised demo gallery
→ review again
```

## Inputs

- Original P55 demo brief library, for example `docs/operations/p55-demo-briefs.json`
- P56 feedback summary, for example `outputs/demo-gallery/review_feedback_summary.json`

## Outputs

At the selected output root:

- `revised_demo_briefs.json`
- `feedback_patch_summary.json`
- `feedback_regeneration_report.md`
- `revised-gallery/index.html`
- `revised-gallery/demo_gallery.json`
- one revised P54 workspace per regenerated demo

## Local command

```bash
python -m src.p57_feedback_regeneration_gallery \
  docs/operations/p55-demo-briefs.json \
  outputs/demo-gallery/review_feedback_summary.json \
  --output-root outputs/feedback-regeneration \
  --overwrite
```

Then open:

```text
outputs/feedback-regeneration/revised-gallery/index.html
```

## Behavior

By default, P57 regenerates items present in the P56 revision queue. That normally includes demos marked `revise` and `reject`.

Use this flag to skip rejected items:

```bash
--exclude-rejected
```

## How feedback changes briefs

P57 does not use an external LLM or hidden model call. It deterministically patches briefs by:

- adding requested changes to `must_use_points`;
- adding reviewer issues into `avoid` notes;
- adding revision context into `source_notes`;
- adding `revision_source` metadata;
- marking revised demo IDs with a `-revised` suffix.

## Review purpose

Use the revised gallery to compare whether feedback actually improved the generated content pack.

Reviewers should check:

- Does the revised hook feel less generic?
- Did requested changes appear in the new script/storyboard?
- Are rights/safety concerns clearer?
- Is the revised pack more useful for an editor?
- Should the revised demo now move to production, another revision, or rejection?

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, or automated final approval is introduced.

The output is local JSON, Markdown, and static HTML only.
