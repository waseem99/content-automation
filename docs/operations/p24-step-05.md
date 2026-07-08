# P24 Step 05

This step documents the operator workflow for reviewing a generated `content_package.json`.

Part of #326. Closes #336 after the PR merges.

## Goal

Give a content operator a clear, repeatable review path for understanding what a generated package contains, what is ready for internal review, what is missing, and what must still pass through packaging, rights, platform export, and editorial approval before any publish-ready decision.

## Source references

This workflow builds on:

```text
docs/operations/p24-step-01.md
docs/operations/p24-step-02.md
docs/operations/p24-step-03.md
docs/operations/p24-step-04.md
src/content_package.py
docs/operations/p24-content-package-short-example.json
docs/operations/p24-content-package-explainer-example.json
tests/integration/test_p24_step_05.py
.github/workflows/p1-acceptance-harness.yml
```

## Workflow status

This operator workflow is documentation-only.

It does not:

- approve content;
- approve rights;
- approve monetization;
- approve editorial status;
- generate packaging assets;
- generate retention scores;
- generate platform export folders;
- render videos;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Operator review sequence

1. Locate the generated `content_package.json` in the production folder.
2. Confirm `schema_version` is `p24.content_package.v1`.
3. Confirm `content_status` is `package_generated` or another non-approved status.
4. Review `run_identity` to confirm the run folder, source command, campaign id, concept id, owner role, and reviewer role.
5. Review `source_assets` to understand source footage, manifests, concept files, clip pools, background music, and rights states.
6. Review `generated_assets` to confirm detected plans, visuals, audio, captions, rendered outputs, source evidence, and checkpoints.
7. Review `platform_suitability` to understand what can be reviewed now and what remains missing per platform.
8. Review `missing_assets` to identify work that must move into P25, P26, P27, P28, or P29.
9. Review `packaging` and `retention` to confirm P25 items are still pending.
10. Review `rights_and_monetization` to confirm `publish_allowed` remains `false` until P26 is complete.
11. Review `exports` to confirm P27 platform export folders are not assumed to exist.
12. Review `editorial_review` to confirm approval state remains `not_approved` until P29 is complete.
13. Review `next_actions` to decide the next responsible owner and target epic.
14. Review `guardrails` before any manual handoff.

## Field meaning guide

| Field | Operator meaning |
| --- | --- |
| `run_identity` | Where the package came from and which command/run produced it. |
| `source_assets` | Input and source evidence that may carry rights, factual, or lineage risk. |
| `generated_assets` | Current detected outputs, including plans, visuals, audio, captions, renders, evidence, and checkpoints. |
| `platform_suitability` | Platform-level review state, missing files, and publish-readiness gaps. |
| `missing_assets` | Work not yet produced by the package generator. |
| `packaging` | P25 title, first-frame, thumbnail, hook, and CTA placeholders. |
| `retention` | P25 retention scoring placeholders. |
| `rights_and_monetization` | P26 risk and rights placeholders; must block publish until reviewed. |
| `exports` | P27 platform export placeholders; paths are not real exports until generated. |
| `editorial_review` | P29 approval state and blockers. |
| `next_actions` | Owner-visible next steps. |
| `guardrails` | Safety rules that must remain attached to the package. |

## Expected safe statuses

Safe initial package statuses:

- `package_generated`;
- `draft_contract_example`;
- `pending_p25`;
- `pending_p26`;
- `pending_p27`;
- `pending_p29`;
- `not_approved`;
- `not_publish_ready`;
- `review_required`;
- `review_only`.

Unsafe statuses or claims before later epics:

- `publish_ready`;
- `approved_for_upload`;
- `rights_cleared`;
- `monetization_approved`;
- `editorial_approved`;
- `platform_export_ready`;
- `publication_eligible: true` for preview renders.

## Short review checklist

For Shorts, the operator must check:

- `production_plan.json` exists and matches the intended topic;
- `manifest.json` exists and references the selected clips;
- `clip_*.mp4` entries are treated as unreviewed source footage;
- `preview_video.mp4` is review-only and not publication eligible;
- `publish_video.mp4`, if present, is still not upload-approved;
- `image_sources.json` is source evidence, not copyright clearance;
- title options are missing until P25;
- first-frame options are missing until P25;
- retention score is missing until P25;
- monetization risk report is missing until P26;
- platform export folders are missing until P27;
- editorial approval is missing until P29.

## Explainer review checklist

For explainers, the operator must check:

- `explainer_plan.json` exists and matches the intended concept;
- `concept.yaml` exists when available;
- clip pool `manifest.json` exists when available;
- `beat_*.png` and `beat_comparison_collage.png` are review assets;
- `narration_*.mp3` files are review assets;
- `subtitles.srt` exists when captions were generated;
- `checkpoint.json` is operator evidence only;
- `final_video.mp4` is not automatically publish-ready;
- factual source review is still required;
- rights and originality review are still required;
- true YouTube long-form readiness still requires P28 planning.

## Package is not publish approval

Creating `content_package.json` means only that the current run has a structured review manifest.

It does not mean:

- the content is safe to publish;
- the content is approved for YouTube;
- the content is approved for TikTok;
- the content is approved for Instagram;
- the content is approved for Facebook;
- the content is approved for X/Twitter;
- broadcast footage is rights-cleared;
- web images are copyright-cleared;
- music is licensed for all platforms;
- claims and stats are fact-checked;
- the video is monetization-ready;
- an editor has approved the package.

## Handoff rules

A package may move to P25 when:

- current production assets are detected;
- topic or concept is clear;
- package shape is valid;
- packaging placeholders are pending.

A package may move to P26 when:

- source assets are visible;
- image source evidence is visible if images exist;
- music and footage require review;
- `publish_allowed` is still `false`.

A package may move to P27 when:

- platform suitability is documented;
- packaging/risk placeholders are visible;
- exports are still pending.

A package may move to P29 when:

- packaging, rights, retention, and exports are ready for human review;
- editorial blockers are visible;
- approval state remains `not_approved` before review.

## Stop conditions

Stop operator workflow work if:

- package creation is treated as publish approval;
- `preview_video.mp4` is selected for upload;
- `image_sources.json` is treated as copyright clearance;
- broadcast clips are treated as rights-cleared by default;
- music is assumed safe across every platform;
- platform export folders are implied before P27;
- editorial approval is implied before P29;
- monetization approval is implied before P26;
- upload or publishing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic rendering.
- No automatic publishing.
- No automatic upload.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic legal approval.
- No automatic platform export.
- No automatic editorial approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.

## Validation

Covered by:

```text
tests/integration/test_p24_step_05.py
```

The validation checks the operator review sequence, field meanings, safe and unsafe statuses, Shorts checklist, explainer checklist, package-not-approval warnings, handoff rules, stop conditions, guardrails, and P24 CI wildcard coverage.
