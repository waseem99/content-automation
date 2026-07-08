# P25 Step 04

This step defines and implements the initial deterministic `retention_score.json` report.

Part of #327. Closes #341 after the PR merges.

## Goal

Create a review-oriented retention report that can evaluate generated football content before final operator approval, using deterministic placeholder scoring first and leaving future YouTube Analytics or AI scoring out of scope.

## Source references

This retention score work builds on:

```text
docs/operations/p24-step-03.md
docs/operations/p24-step-05.md
docs/operations/p25-step-01.md
docs/operations/p25-step-02.md
docs/operations/p25-step-03.md
src/content_package.py
src/retention_score.py
docs/operations/p25-retention-score-example.json
tests/integration/test_p25_step_04.py
.github/workflows/p1-acceptance-harness.yml
```

## Implementation status

The retention score helper is deterministic and review-focused.

It does:

- define `retention_score.json` schema;
- generate placeholder scores for hook strength;
- generate placeholder scores for first 1 second thumb-stop strength;
- generate placeholder scores for first 3 seconds clarity;
- generate placeholder scores for first 8 seconds retention lock;
- generate placeholder scores for curiosity gap;
- generate placeholder scores for visual pacing;
- generate placeholder scores for midpoint reset;
- generate placeholder scores for CTA strength;
- generate `dead_air_risk`;
- generate `genericness_risk`;
- generate recommended fixes;
- provide a package integration helper for the P24 `retention` section;
- write a deterministic JSON report.

It does not:

- ingest YouTube Analytics;
- run A/B tests;
- call AI scoring services;
- predict real retention curves;
- approve publishing;
- approve monetization;
- approve rights;
- approve editorial status;
- upload to YouTube;
- publish content;
- bypass workflow gates.

## retention_score.json schema

Each report must include:

- `schema_version`;
- `package_id`;
- `content_type`;
- `source_topic`;
- `hook_text`;
- `cta_text`;
- `hook_score`;
- `first_1s_thumb_stop_score`;
- `first_3s_clarity_score`;
- `first_8s_retention_lock_score`;
- `curiosity_gap_score`;
- `visual_pacing_score`;
- `midpoint_reset_score`;
- `cta_strength_score`;
- `average_core_score`;
- `dead_air_risk`;
- `genericness_risk`;
- `recommended_fixes`;
- `status`;
- `approval_state`;
- `planned_epic`;
- `notes`.

## Risk labels

Allowed risk labels:

- `low`;
- `medium`;
- `high`.

`dead_air_risk` must reflect visual pacing risk.

`genericness_risk` must reflect hook and topic specificity risk.

## Package integration path

The helper `apply_retention_score_to_package` updates the P24 package `retention` section with:

- `retention_score_path`;
- `hook_score`;
- `first_three_seconds_score`;
- `midpoint_reset_score`;
- `cta_strength_score`;
- `dead_air_risk`;
- `genericness_risk`;
- `recommended_fixes`;
- `status: generated_pending_review`;
- `planned_epic: P25`.

This integration does not approve the package or make it publish-ready.

## Recommended fixes

Reports should include recommended fixes when weak areas are detected:

- open with a more specific football moment, player, or consequence;
- add a stronger first-frame visual interruption or high-contrast caption;
- add a midpoint reset such as a stat card, comparison, timeline jump, or “but then” turn;
- replace the ending with a debate, prediction, ranking, loyalty, legacy, or versus question;
- review for factual support, rights safety, and editorial alignment before use.

## Example report

Example output is stored at:

```text
docs/operations/p25-retention-score-example.json
```

The example includes all required score fields, risk labels, recommended fixes, and review-only notes.

## Stop conditions

Stop retention report work if:

- scores are described as real YouTube Analytics data;
- scores are described as A/B test results;
- a score automatically approves content;
- a score automatically approves monetization;
- a score automatically clears rights;
- a score automatically approves editorial status;
- `publish_allowed` is changed to `true`;
- upload or publishing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No YouTube Analytics ingestion.
- No automated A/B testing.
- No automatic retention approval.
- No automatic publishing approval.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic editorial approval.
- No automatic upload.
- No automatic publishing.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p25_step_04.py
```

The validation checks report schema fields, deterministic scoring, risk labels, recommended fixes, package integration, report writing, stop conditions, guardrails, and P25 CI wildcard coverage.
