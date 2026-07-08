# P25 Step 02

This step defines and stubs YouTube title options for generated content packages.

Part of #327. Closes #339 after the PR merges.

## Goal

Add a structured title-option contract so operators receive multiple reviewable YouTube title options connected to the content topic instead of only receiving a generated video file.

## Source references

This title option work builds on:

```text
docs/operations/p24-step-03.md
docs/operations/p24-step-05.md
docs/operations/p25-step-01.md
src/content_package.py
src/title_options.py
docs/operations/p25-title-options-example.json
tests/integration/test_p25_step_02.py
.github/workflows/p1-acceptance-harness.yml
```

## Implementation status

The title option helper is deterministic and review-focused.

It does:

- define a structured title option schema;
- generate 10 title option stubs per topic;
- support curiosity, debate, nostalgia, record chase, shock, explainer, legacy, pressure, versus, and prediction styles;
- attach an emotional trigger to each option;
- attach risk notes to each option;
- mark each option as `not_approved`;
- avoid external API calls;
- provide an example packaging output.

It does not:

- approve titles;
- upload titles to YouTube;
- run YouTube A/B tests;
- generate thumbnails;
- generate first-frame images;
- score retention;
- verify facts;
- approve monetization;
- approve rights;
- publish content;
- bypass workflow gates.

## Title option schema

Each title option must include:

- `option_id`;
- `title_text`;
- `title_style`;
- `angle`;
- `emotional_trigger`;
- `platform_fit`;
- `source_topic`;
- `content_type`;
- `risk_notes`;
- `approval_state`.

## Required title styles

The supported title styles are:

- `curiosity`;
- `debate`;
- `nostalgia`;
- `record_chase`;
- `shock`;
- `explainer`;
- `legacy`;
- `pressure`;
- `versus`;
- `prediction`.

## Example title option output

Example output is stored at:

```text
docs/operations/p25-title-options-example.json
```

The example includes at least 10 title options for a football topic and shows how title options fit under the P24 `packaging.title_options` field.

## Topic connection requirement

Every generated title option must remain connected to the source topic.

The option must include:

- the original `source_topic`;
- a title that includes the subject or topic phrase;
- a content type value such as `short`, `explainer`, or `long_form`;
- a risk note requiring editorial review.

## Risk rules

Title options must avoid:

- misleading clickbait;
- unsupported injury claims;
- unsupported scandal claims;
- fabricated football facts;
- fake certainty about future outcomes;
- personal attacks on players, teams, fans, or communities;
- implying rights, monetization, or editorial approval.

## Operator review rules

Before any title can be used externally, an operator must confirm:

- the title matches the script or concept;
- the title does not overstate the facts;
- the title is not misleading;
- the title does not imply unsupported controversy;
- the title is appropriate for YouTube Shorts or YouTube long-form;
- the title aligns with the first frame, thumbnail, hook, and CTA;
- the title remains marked `not_approved` until editorial review.

## Stop conditions

Stop title option work if:

- title options are marked approved automatically;
- title options are uploaded to YouTube;
- a title claims a fact not present in the script or source evidence;
- a title implies injury, scandal, or controversy without review;
- title generation calls external services inside deterministic tests;
- title work generates thumbnails or first-frame images;
- YouTube A/B testing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No misleading clickbait.
- No unsupported claims.
- No fabricated football facts.
- No automatic title approval.
- No automatic upload.
- No automatic publishing.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic editorial approval.
- No YouTube API A/B testing.
- No thumbnail generation in this step.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p25_step_02.py
```

The validation checks schema fields, required styles, deterministic output count, source topic alignment, example package output, risk notes, approval state, guardrails, and P25 CI wildcard coverage.
