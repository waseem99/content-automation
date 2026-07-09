# P26 Step 05

This step defines publish-block rules for high-risk football content packages.

Part of #328. Closes #348 after the PR merges.

## Goal

Define workflow controls that prevent generated content from being marked publish-ready when asset, originality, music, image, source, rights, or editorial risks remain unresolved.

## Source references

This publish-block model builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-step-01.md
docs/operations/p26-step-02.md
docs/operations/p26-step-03.md
docs/operations/p26-step-04.md
docs/operations/p26-publish-block-examples.json
src/content_package.py
tests/integration/test_p26_step_05.py
.github/workflows/p1-acceptance-harness.yml
```

## Rule status

This publish-block model is a workflow control.

It is not:

- legal clearance;
- copyright clearance;
- monetization approval;
- platform approval;
- editorial approval;
- direct platform enforcement;
- automatic content removal;
- automatic publishing;
- automatic upload;
- workflow gate bypass.

## Required publish decision fields

Every publish decision record must include:

- `decision_id`;
- `package_id`;
- `content_type`;
- `publish_allowed`;
- `review_required`;
- `decision_state`;
- `hard_blockers`;
- `non_blocking_warnings`;
- `blocking_reasons`;
- `required_actions`;
- `p29_editorial_required`;
- `reviewer_role`;
- `notes`.

## Allowed decision states

Allowed `decision_state` values:

- `blocked_until_review`;
- `blocked_until_revision`;
- `review_required`;
- `export_candidate_after_review`;
- `not_publish_ready`.

A decision state must not imply public release approval.

## Hard blockers

The following conditions must force `publish_allowed: false`:

- `unreviewed_broadcast_footage`;
- `unreviewed_extracted_clip`;
- `missing_image_attribution`;
- `unknown_image_license`;
- `unverified_music_license`;
- `missing_stat_source_reference`;
- `high_reused_content_risk`;
- `missing_originality_layer`;
- `missing_human_editorial_approval`;
- `missing_p29_publish_readiness_manifest`;
- `unreviewed_ai_likeness_or_logo_risk`;
- `source_evidence_treated_as_clearance`;
- `platform_export_requested_before_review`;
- `legal_or_monetization_approval_implied`.

## Non-blocking warnings

The following warnings may be non-blocking only when no hard blocker remains:

- `minor_caption_cleanup_needed`;
- `optional_description_attribution_improvement`;
- `low_confidence_title_variant`;
- `thumbnail_concept_needs_polish`;
- `cta_could_be_stronger`;
- `retention_score_medium_risk`;
- `internal_evidence_link_missing_pr_reference`.

Non-blocking warnings must still be visible in the package and risk report.

## Blocking condition details

### Unreviewed broadcast footage

Any broadcast clip, match highlight, match still, or extracted source clip with unresolved rights must block publishing.

Required action:

- confirm rights or permission;
- confirm commentary and transformation context;
- confirm duration and platform risk;
- replace or remove the asset if review cannot clear it.

### Missing image attribution or unknown image license

Any web image with unknown license, unknown attribution requirement, missing source page, or unresolved player/logo/trademark risk must block publishing.

Required action:

- verify source URL;
- verify license terms;
- record attribution text when needed;
- record attribution placement;
- replace the asset if attribution or license cannot be verified.

### Unverified music license

Any music or sound asset with unknown commercial/social/platform coverage must block publishing.

Required action:

- confirm YouTube coverage;
- confirm TikTok coverage;
- confirm Instagram coverage;
- confirm Facebook coverage;
- confirm X/Twitter coverage;
- remove or replace music if platform coverage is unclear.

### Missing source references

Any statistic, claim, ranking, factual comparison, or caption claim without source references must block publishing.

Required action:

- add source URL;
- record checked date;
- align the claim with the source;
- remove the claim if source support is missing.

### High reused-content risk

A package with raw clips, generic narration, low originality, or slideshow-style assembly must block publishing.

Required action:

- add original analysis;
- add a unique narration angle;
- add sourced comparison;
- add custom stat card or visual structure;
- add a specific CTA or debate frame;
- complete originality review.

### Missing human approval

No package can be publish-ready before P29 editorial governance exists and a human reviewer approves the publish-readiness manifest.

Required action:

- complete P29 editorial review;
- confirm rights review;
- confirm source review;
- confirm packaging review;
- confirm export pack review;
- record approval evidence without secrets.

## Required report fields

`monetization_risk_report.json` and future publish readiness reports must include:

- `publish_allowed`;
- `review_required`;
- `blocking_reasons`;
- `required_actions`;
- `hard_blockers`;
- `non_blocking_warnings`;
- `decision_state`;
- `p29_editorial_required`.

## Alignment with P29 editorial workflow

P26 publish-block rules must align with P29 by requiring:

- editorial status model;
- human review checklist;
- publish-readiness manifest;
- render-mode approval rules;
- editorial evidence trail;
- final approval state.

Until P29 is complete, `missing_p29_publish_readiness_manifest` and `missing_human_editorial_approval` remain hard blockers.

## Example publish decisions

Example blocked and allowed-after-review states are stored at:

```text
docs/operations/p26-publish-block-examples.json
```

The examples include:

- a blocked high-risk package;
- a review-required medium-risk package;
- an export-candidate-after-review package that still does not imply automatic publishing.

## Stop conditions

Stop publish-block work if:

- a high-risk example has `publish_allowed: true`;
- unreviewed broadcast footage is non-blocking;
- unverified music is non-blocking;
- missing image attribution is non-blocking;
- missing source references are non-blocking;
- missing originality is non-blocking;
- missing human editorial approval is non-blocking;
- P29 approval is bypassed;
- direct platform enforcement is introduced;
- auto-removing risky content is introduced;
- workflow gate bypass is requested.

## Guardrails

- No legal clearance implied.
- No copyright clearance implied.
- No monetization approval implied.
- No platform approval implied.
- No editorial approval implied.
- No direct platform enforcement.
- No auto-removing risky content.
- No automatic upload.
- No automatic publishing.
- No automatic rights clearance.
- No automatic monetization approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p26_step_05.py
```

The validation checks required publish decision fields, decision states, hard blockers, non-blocking warnings, blocking condition details, required report fields, P29 alignment, example blocked and allowed-after-review states, stop conditions, guardrails, and P26 CI wildcard coverage.
