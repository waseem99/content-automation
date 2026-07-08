# P25 Step 05

This step defines the football CTA and comment-trigger library.

Part of #327. Closes #342 after the PR merges.

## Goal

Create reusable CTA and comment-trigger options for football Shorts and explainers so generated endings drive debate, prediction, ranking, loyalty, legacy, and versus conversations instead of generic subscribe/follow prompts.

## Source references

This CTA library work builds on:

```text
docs/operations/p24-step-03.md
docs/operations/p24-step-05.md
docs/operations/p25-step-01.md
docs/operations/p25-step-02.md
docs/operations/p25-step-03.md
docs/operations/p25-step-04.md
src/cta_library.py
docs/operations/p25-cta-library-example.json
tests/integration/test_p25_step_05.py
.github/workflows/p1-acceptance-harness.yml
```

## Implementation status

The CTA helper is deterministic and review-focused.

It does:

- define a CTA/comment-trigger schema;
- generate debate CTAs;
- generate prediction CTAs;
- generate loyalty CTAs;
- generate ranking CTAs;
- generate controversy CTAs;
- generate legacy CTAs;
- generate versus CTAs;
- attach intent and comment-trigger notes;
- attach risk notes;
- mark each CTA as `not_approved`;
- provide a package integration helper for `packaging.cta_comment_trigger_options`.

It does not:

- does not scrape comments;
- does not moderate communities;
- does not post comments;
- does not upload to YouTube;
- does not publish content;
- does not approve CTAs;
- does not approve editorial status;
- does not approve monetization;
- does not clear rights;
- does not bypass workflow gates.

## CTA option schema

Each CTA option must include:

- `cta_id`;
- `cta_type`;
- `cta_text`;
- `source_topic`;
- `content_type`;
- `focal_subject`;
- `intent`;
- `comment_trigger`;
- `platform_fit`;
- `risk_notes`;
- `approval_state`.

## Required CTA types

Supported CTA types:

- `debate`;
- `prediction`;
- `loyalty`;
- `ranking`;
- `controversy`;
- `legacy`;
- `versus`.

## CTA type meaning

| CTA type | Purpose | Example |
| --- | --- | --- |
| `debate` | Invite respectful disagreement. | “Be honest: are fans too harsh on Neymar?” |
| `prediction` | Ask what happens next. | “What happens next for Neymar?” |
| `loyalty` | Activate fan identity. | “Neymar fans, are you still backing this story?” |
| `ranking` | Push viewers to compare by one dimension. | “Rank Neymar by pressure, not talent.” |
| `controversy` | Frame a safe disagreement without unsupported scandal. | “Is the conversation around Neymar fair or exaggerated?” |
| `legacy` | Connect the video to long-term reputation. | “Does this change how you see Neymar’s legacy?” |
| `versus` | Invite comparison without false certainty. | “Who carries more pressure than Neymar right now?” |

## Packaging integration path

The helper `apply_cta_options_to_packaging` updates the P24 package `packaging` section with:

- `cta_comment_trigger_options`;
- `status: generated_pending_review`;
- `planned_epic: P25`.

This integration does not approve the CTA, package, title, thumbnail, retention score, rights status, monetization status, or editorial status.

## Example library output

Example output is stored at:

```text
docs/operations/p25-cta-library-example.json
```

The example includes all seven required CTA types and shows how they fit under `packaging.cta_comment_trigger_options`.

## Risk rules

CTA options must avoid:

- unsupported claims;
- harassment;
- inflammatory wording;
- abusive fan-baiting;
- personal attacks on players, teams, fans, or communities;
- fake scandal framing;
- fake injury framing;
- hate, slurs, or protected-class targeting;
- implying rights, monetization, or editorial approval.

## Operator review rules

Before a CTA can be used externally, an operator must confirm:

- the CTA matches the script and final segment;
- the CTA does not make unsupported claims;
- the CTA does not encourage abuse;
- the CTA is framed as a football debate, prediction, ranking, loyalty, legacy, or versus question;
- the CTA aligns with the title, hook, first frame, and thumbnail concept;
- the CTA remains marked `not_approved` until editorial review.

## Stop conditions

Stop CTA work if:

- CTA options are marked approved automatically;
- CTA options scrape comments;
- CTA options post comments;
- CTA options target harassment toward a player, team, fanbase, or community;
- CTA options imply fake injury, scandal, or controversy;
- upload or publishing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No unsupported claims.
- No harassment.
- No inflammatory wording.
- No abusive fan-baiting.
- No fake injury framing.
- No fake scandal framing.
- No automatic CTA approval.
- No comment scraping.
- No comment posting.
- No automatic upload.
- No automatic publishing.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic editorial approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p25_step_05.py
```

The validation checks schema fields, required CTA categories, deterministic CTA generation, package integration, example library output, risk notes, approval state, stop conditions, guardrails, and P25 CI wildcard coverage.
