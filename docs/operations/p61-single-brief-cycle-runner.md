# P61 Single-Brief Full Review Cycle Runner

Part of #659. Closes #660–#665 after merge.

## What this builds

P61 runs the current local content creator workflow from one brief JSON in one command.

It combines:

```text
single custom brief
→ P60 adapter files
→ P58 full review cycle
→ P61 master index and report
```

## Local command

```bash
python -m src.p61_single_brief_cycle_runner \
  outputs/creator-studio/sample_brief.json \
  --output-root outputs/single-brief-cycle \
  --overwrite
```

Then open:

```text
outputs/single-brief-cycle/single_brief_cycle_index.html
```

## Outputs

At the selected output root:

- `single_brief_cycle_index.html` — master browser-openable local index
- `single_brief_cycle_summary.json` — machine-readable artifact map and counts
- `single_brief_cycle_report.md` — operator report
- `adapter/custom_brief_library.json` — one-item review-cycle brief library
- `adapter/custom_feedback_template.json` — matching feedback template
- `adapter/custom_cycle_manifest.json`
- `adapter/custom_cycle_readme.md`
- `review-cycle/review_cycle_index.html` — full P58 review cycle index

## Review flow

1. Create or export a brief from P59 Creator Studio.
2. Run P61 using that brief JSON.
3. Open `single_brief_cycle_index.html`.
4. Open the full review cycle index.
5. Inspect the generated concept, hook, script, storyboard, rights notes, monetization notes, QA and revisions.
6. Replace placeholder feedback with real human review notes before any production decision.
7. Re-run the cycle after feedback changes if another revision pass is needed.

## Why this matters

P59 made brief drafting easier.
P60 prepared custom brief inputs for the review cycle.
P61 removes the extra manual command by running the custom brief adapter and review cycle together.

This is the most practical local operator path so far:

```text
open Creator Studio
→ export brief JSON
→ run one command
→ open reviewable output in browser
```

## Deployment position

No cloud deployment, hosted UI/API, authentication, database, rendering, asset download, upload, publishing, external call, browser command execution, or automated final approval is introduced.

Human approval remains required before production.
