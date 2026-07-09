# P27 Step 05

This step defines and implements cross-platform export readiness validation for generated football content packages.

Part of #329. Closes #354 after the PR merges.

## Goal

Validate that P27 platform export packs are complete, consistent, risk-aware, and clearly marked as blocked/review-only before any human manual publishing workflow begins.

## Source references

This readiness validation builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-readiness-report.md
docs/operations/p27-step-01.md
docs/operations/p27-step-02.md
docs/operations/p27-step-03.md
docs/operations/p27-step-04.md
src/youtube_shorts_export.py
src/short_form_exports.py
src/x_twitter_export.py
src/export_readiness.py
docs/operations/p27-cross-platform-readiness-example.json
tests/integration/test_p27_step_05.py
```

## Contract status

This step adds validation and example evidence for cross-platform export readiness.

It does not:

- upload to any platform;
- call platform APIs;
- create live post previews;
- render new platform-specific videos;
- commit generated video assets;
- approve rights;
- approve monetization;
- approve facts or stats;
- approve editorial status;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- bypass workflow gates.

## Platforms covered

Validation covers:

- `youtube_shorts`;
- `tiktok`;
- `instagram_reels`;
- `facebook_reels`;
- `x_twitter`.

YouTube long-form is intentionally not included in this readiness validator yet because P28 long-form work remains future scope.

## Required validation checks

The validator checks:

| Area | Requirement |
| --- | --- |
| Required platform packs | All five P27 short/social platform packs must be present. |
| Required files | Each platform pack must include its required files. |
| Platform names | Platform identifiers must match the P27 naming contract. |
| Metadata fields | Common metadata fields must be present and internally consistent. |
| Review status fields | Common review status fields must be present and internally consistent. |
| Risk carry-through | Blocking reasons and required actions must carry from metadata into review status. |
| Risk notes | Risk notes must preserve `publish_allowed: false`, review requirements, and P29/editorial caveats. |
| Platform-specific caveats | Short-form packs must include platform-specific music-risk caveats; X/Twitter must include factual/stat caveats. |
| Publish gating | Blocked or review-only content must not appear as `publish_ready`. |

## Readiness states

A passing readiness report means:

```text
is_ready_for_manual_review: true
is_publish_ready: false
publish_allowed: false
review_required: true
```

Manual-review readiness is not publishing approval.

## Manual publishing workflow

After a cross-platform report passes, the operator should still follow this manual workflow:

1. Review generated copy and metadata per platform.
2. Confirm P26 rights, monetization, source attribution, music, and originality status.
3. Complete P29 editorial approval before any publish-ready state.
4. Prepare any platform upload manually outside the validator only after approvals are recorded.

The validator must not create a live post preview, connect a platform account, or upload content.

## Failure examples

The validation must catch:

- missing platform packs;
- missing required files;
- missing metadata fields;
- inconsistent platform names;
- missing blocking reasons;
- missing required actions;
- missing or inconsistent risk notes;
- `publish_allowed: true` on any pack, metadata, or review status;
- blocked content incorrectly marked as `publish_ready`.

## Example output

Example readiness output is stored at:

```text
docs/operations/p27-cross-platform-readiness-example.json
```

The example includes all five platform results, manual publishing workflow guidance, review-only defaults, and `is_publish_ready: false`.

## Stop conditions

Stop readiness work if:

- validation is treated as publishing approval;
- `publish_allowed` defaults to `true`;
- blocked content is marked `publish_ready`;
- P26 publish-block rules are ignored;
- P29 editorial approval is bypassed;
- platform credentials are requested or stored;
- platform API upload checks are introduced;
- live post previews are introduced;
- external rendered videos are committed;
- secret values are committed;
- workflow gate bypass is requested.

## Guardrails

- No platform upload.
- No platform API checks.
- No live post previews.
- No platform credentials.
- No external video asset commits.
- No secret values.
- No automatic publish approval.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic factual/stat approval.
- No automatic editorial approval.
- No bypass of P26 publish-block rules.
- No bypass of P29 editorial governance.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p27_step_05.py
```

The validation checks required platforms, required files, metadata fields, review status fields, missing file detection, risk-note detection, blocked/publish-ready safeguards, manual publishing workflow documentation, stop conditions, guardrails, and deterministic output behavior.
