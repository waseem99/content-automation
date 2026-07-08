# P26 Step 02

This step defines the `monetization_risk_report.json` contract.

Part of #328. Closes #345 after the PR merges.

## Goal

Define a structured report that summarizes publish, monetization, rights, attribution, originality, and platform-reuse risk for generated football content packages before any platform export or publish-ready decision.

## Source references

This risk report schema builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-step-01.md
src/content_package.py
docs/operations/p26-risk-report-low-example.json
docs/operations/p26-risk-report-medium-example.json
docs/operations/p26-risk-report-high-example.json
tests/integration/test_p26_step_02.py
.github/workflows/p1-acceptance-harness.yml
```

## Schema status

This `monetization_risk_report.json` schema is documentation and contract focused.

It does not:

- provide legal advice;
- clear copyrights;
- predict Content ID claims;
- predict copyright strikes;
- verify licenses automatically;
- enforce platform APIs;
- approve YouTube monetization;
- approve platform publishing;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Required top-level fields

Every `monetization_risk_report.json` must include:

| Field | Purpose |
| --- | --- |
| `schema_version` | Initial value: `p26.monetization_risk_report.v1`. |
| `report_id` | Stable risk report identifier. |
| `package_id` | Related P24 content package identifier. |
| `content_type` | `short`, `explainer`, or future `long_form`. |
| `overall_risk_level` | Overall risk summary. |
| `publish_allowed` | Must default to `false` until all blockers are cleared. |
| `review_required` | Must be `true` when any risk category or asset remains unreviewed. |
| `risk_categories` | Category-level risk review results. |
| `asset_risks` | Asset-level risk entries based on P26-01 classification. |
| `blocking_reasons` | Hard blockers preventing publish-readiness. |
| `required_actions` | Actions needed before export or publish-ready state. |
| `evidence_allowed` | Safe evidence that may be stored in the repository. |
| `evidence_blocked` | Evidence that must remain private or off-repository. |
| `content_package_updates` | Suggested updates to `content_package.json`. |
| `review_state` | Report workflow state. |
| `reviewer_role` | Role responsible for risk review. |
| `notes` | Non-sensitive report notes. |

## Required risk categories

`risk_categories` must include:

- `reused_content_risk`;
- `copyright_risk`;
- `image_license_risk`;
- `music_license_risk`;
- `ai_template_risk`;
- `factual_risk`;
- `originality_risk`;
- `platform_reuse_risk`;
- `brand_safety_risk`.

Each category must include:

- `risk_level`;
- `review_required`;
- `publish_blocking`;
- `reason`;
- `required_actions`.

## Allowed risk labels

Allowed risk labels:

- `low`;
- `medium`;
- `high`;
- `blocked_until_review`;
- `not_applicable`.

## Required asset risk fields

Every `asset_risks` item must include:

- `asset_id`;
- `asset_role`;
- `asset_path`;
- `default_risk_level`;
- `current_risk_level`;
- `review_required`;
- `publish_blocking`;
- `blocking_reasons`;
- `required_actions`;
- `evidence_allowed`;
- `evidence_blocked`;
- `notes`.

## Blocking rules

`publish_allowed` must be `false` when any of these are true:

- any category has `publish_blocking: true`;
- any asset has `publish_blocking: true`;
- broadcast footage is unreviewed;
- extracted clips are unreviewed;
- music license is unverified;
- web image license or attribution is unverified;
- AI image provenance or likeness risk is unreviewed;
- factual claims or stats are unsourced;
- originality assessment is missing;
- editorial approval is missing;
- source evidence is treated as rights clearance;
- platform export is requested before risk review.

## content_package.json linkage

`content_package_updates` must include suggested values for the P24 package `rights_and_monetization` section:

- `monetization_risk_report_path`;
- `publish_allowed`;
- `review_required`;
- `rights_clearance_status`;
- `source_attribution_status`;
- `music_license_status`;
- `originality_status`;
- `blocking_reasons`;
- `required_actions`;
- `status`;
- `planned_epic`.

This linkage does not approve the package or make it publish-ready.

## Example reports

Example reports are stored at:

```text
docs/operations/p26-risk-report-low-example.json
docs/operations/p26-risk-report-medium-example.json
docs/operations/p26-risk-report-high-example.json
```

The low-risk example is still review-required and not publish-approved.

The medium-risk example includes unresolved review actions.

The high-risk example is blocked until review.

## Stop conditions

Stop risk report work if:

- `publish_allowed` defaults to `true`;
- a low-risk report is treated as publish approval;
- broadcast footage is treated as rights-cleared by default;
- unverified music is treated as safe;
- web image filtering is treated as legal clearance;
- `image_sources.json` is treated as copyright clearance;
- platform upload is introduced;
- legal clearance is implied;
- monetization approval is implied;
- workflow gate bypass is requested.

## Guardrails

- No automated legal clearance.
- No copyright claim prediction.
- No Content ID prediction.
- No automatic license verification.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic publishing approval.
- No automatic upload.
- No automatic publishing.
- No platform API enforcement.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p26_step_02.py
```

The validation checks required top-level fields, required risk categories, allowed risk labels, asset risk fields, low/medium/high example reports, blocking rules, `content_package.json` linkage, stop conditions, guardrails, and P26 CI wildcard coverage.
