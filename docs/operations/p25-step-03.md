# P25 Step 03

This step defines first-frame and thumbnail concept outputs for generated football content packages.

Part of #327. Closes #340 after the PR merges.

## Goal

Create structured visual concept options so each video can be reviewed with a stronger YouTube Shorts first-frame package and a future YouTube long-form thumbnail package before any upload or publish workflow.

## Source references

This visual concept work builds on:

```text
docs/operations/p24-step-03.md
docs/operations/p24-step-05.md
docs/operations/p25-step-01.md
docs/operations/p25-step-02.md
src/title_options.py
src/visual_concepts.py
docs/operations/p25-visual-concepts-example.json
tests/integration/test_p25_step_03.py
.github/workflows/p1-acceptance-harness.yml
```

## Implementation status

The visual concept helper is deterministic and review-focused.

It does:

- define first-frame concept schema;
- define thumbnail concept schema;
- generate first-frame options for YouTube Shorts review;
- generate thumbnail concepts for YouTube long-form and Shorts packaging review;
- include visual layout guidance;
- include suggested text;
- include emotion;
- include focal subject;
- include contrast idea;
- include risk notes;
- mark each concept as `not_approved`;
- avoid external image-generation APIs;
- avoid rendering thumbnails or first-frame images.

It does not:

- does not render actual thumbnails;
- does not generate images;
- does not call image-generation APIs;
- does not approve visual assets;
- does not verify image rights;
- does not upload to YouTube;
- does not publish content;
- does not bypass workflow gates.

## Visual concept schema

Each first-frame or thumbnail concept must include:

- `concept_id`;
- `concept_type`;
- `source_topic`;
- `content_type`;
- `platform_fit`;
- `visual_pattern`;
- `visual_layout`;
- `suggested_text`;
- `emotion`;
- `focal_subject`;
- `contrast_idea`;
- `risk_notes`;
- `approval_state`.

## Concept types

Supported concept types:

- `first_frame`;
- `thumbnail`.

`first_frame` concepts are primarily for YouTube Shorts and other vertical short-form platforms.

`thumbnail` concepts are primarily for YouTube long-form and future thumbnail packaging review.

## Required football-specific visual patterns

The supported football-specific visual patterns are:

- `freeze_frame_punch_in`;
- `split_screen_debate`;
- `injury_goal_reaction_frame`;
- `stat_card_frame`;
- `legacy_vs_future_frame`.

## Pattern meaning

| Pattern | Use |
| --- | --- |
| `freeze_frame_punch_in` | Use when a tackle, goal, save, miss, or celebration can stop the scroll. |
| `split_screen_debate` | Use when the video is built around disagreement, rivalry, ranking, or pressure comparison. |
| `injury_goal_reaction_frame` | Use when the emotional reaction matters more than the raw event. |
| `stat_card_frame` | Use when one number or record creates the curiosity gap. |
| `legacy_vs_future_frame` | Use when the story compares past greatness with future pressure. |

## First-frame requirements

A first-frame concept must:

- work with sound off;
- make the subject visually clear within one second;
- include a visual interruption or strong emotion;
- include short suggested text;
- avoid clutter;
- align with the title and hook;
- remain subject to image and rights review.

## Thumbnail requirements

A thumbnail concept must:

- support 16:9 long-form packaging;
- include a clear focal subject;
- include visual contrast;
- include short suggested text;
- create curiosity without misleading claims;
- align with the title, hook, and video promise;
- remain subject to image and rights review.

## Example visual concept output

Example output is stored at:

```text
docs/operations/p25-visual-concepts-example.json
```

The example includes multiple first-frame options and multiple thumbnail concepts tied to a football topic.

## Risk rules

Visual concepts must avoid:

- misleading visual claims;
- fake injuries or fake controversies;
- unlicensed player images;
- unlicensed broadcast stills;
- unlicensed club or tournament logos;
- implying rights clearance;
- implying editorial approval;
- implying monetization approval;
- cluttered visual layouts that weaken retention.

## Operator review rules

Before a concept can be used externally, an operator must confirm:

- the visual concept matches the script or concept;
- the suggested text matches the title and hook;
- the focal subject is correct;
- the concept does not imply unsupported injury, scandal, or controversy;
- source imagery has rights review;
- player, club, league, and tournament marks are handled safely;
- the concept remains marked `not_approved` until editorial review.

## Stop conditions

Stop visual concept work if:

- visual concepts are marked approved automatically;
- thumbnails are rendered in this step;
- first-frame images are rendered in this step;
- image-generation APIs are called;
- unlicensed player images are treated as safe;
- broadcast stills are treated as rights-cleared;
- a concept implies a false injury, scandal, or controversy;
- upload or publishing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No misleading visual claims.
- No fake injuries.
- No fake scandals.
- No automatic visual approval.
- No automatic image generation.
- No thumbnail rendering in this step.
- No first-frame rendering in this step.
- No automatic upload.
- No automatic publishing.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic editorial approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p25_step_03.py
```

The validation checks schema fields, required visual patterns, first-frame requirements, thumbnail requirements, deterministic concept generation, example output, risk notes, approval state, guardrails, and P25 CI wildcard coverage.
