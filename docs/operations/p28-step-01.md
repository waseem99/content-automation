# P28 Step 01

This step defines the long-form 16:9 concept model for 6–8 minute YouTube football videos.

Part of #330. Closes #356 after the PR merges.

## Goal

Create a deterministic planning contract for long-form football videos that can support serious YouTube channel strategy while remaining compatible with Shorts cutdowns and P27 platform export packaging.

## Contract status

This step adds schema, example, and validation coverage only.

It does not:

- render a long-form video;
- implement a `produce-longform` command;
- upload to YouTube;
- connect YouTube Studio;
- ingest analytics;
- clear rights;
- approve monetization;
- approve editorial status;
- bypass P26 or P29 gates.

## Required concept fields

A valid long-form concept includes:

| Field | Purpose |
| --- | --- |
| `schema_version` | Contract version. |
| `content_type` | `youtube_long_form`. |
| `format` | 16:9 planning target. |
| `topic` | Football story/topic being planned. |
| `subject` | Main player, club, match, tournament, or story subject. |
| `audience` | Target viewer segment. |
| `central_question` | Main question the 6–8 minute video answers. |
| `target_duration_minutes` | Planned video length, constrained to 6–8 minutes. |
| `target_duration_seconds` | Duration in seconds. |
| `source_requirements` | Minimum sourcing, factual review, attribution, and rights requirements. |
| `visual_style` | 16:9 visual approach and rights-safe B-roll rules. |
| `sponsor_slot_markers` | Placeholder-only sponsorship slots. |
| `chapters` | Ordered chapter/section plan. |
| `shorts_compatibility` | Cutdown compatibility for Shorts and P27 exports. |
| `platform_packaging` | YouTube long-form packaging and Shorts funnel markers. |
| `publish_allowed` | Always `false` at this stage. |
| `review_required` | Always `true` at this stage. |

## Section types

The long-form chapter sequence is:

1. `cold_open`
2. `question`
3. `context`
4. `conflict`
5. `turning_point`
6. `payoff`
7. `comment_trigger`

Each chapter includes:

- `section_type`;
- `title`;
- `narrative_goal`;
- `target_duration_seconds`;
- `visual_direction`;
- `source_notes`;
- `shorts_cutdown_candidate`.

## Source requirements

The concept must require:

- at least three sources;
- official match or competition records where available;
- reliable match reports or archives;
- rights-reviewed visual sources or recreated editorial visuals;
- factual review;
- source attribution;
- rights review before any production or cutdown packaging.

## Sponsor slot markers

Sponsor slots are placeholders only. They do not activate sponsorship, monetization, ad insertion, or publishing approval.

The concept supports:

- `midroll_after_context`;
- `pre_payoff_soft_mention`.

Both remain `placeholder_only` until a later scoped workflow approves sponsorship and editorial treatment.

## Shorts and P27 compatibility

The concept includes `shorts_compatibility` so long-form planning can identify sections that may later become Shorts cutdowns.

Compatibility does not mean automatic export or publishing. Any cutdown must preserve:

- P26 risk state;
- rights review;
- monetization review;
- source attribution;
- editorial approval;
- P27 platform packaging review-only defaults.

## Example output

Example long-form concept output is stored at:

```text
docs/operations/p28-long-form-concept-example.json
```

## Validation

Validation is implemented in:

```text
src/long_form_concept.py
tests/integration/test_p28_step_01.py
```

The validator checks:

- required top-level fields;
- 16:9 format;
- 6–8 minute target duration;
- audience and central question presence;
- source requirements;
- visual style requirements;
- sponsor slot placeholders;
- ordered chapter section types;
- Shorts cutdown compatibility;
- P27 packaging compatibility after review;
- `publish_allowed: false`;
- `review_required: true`;
- direct upload remains out of scope.

## Stop conditions

Stop work if a future change attempts to:

- render a long-form video in this step;
- introduce YouTube upload APIs;
- connect YouTube Studio analytics;
- treat this concept as editorial approval;
- set `publish_allowed` to `true`;
- skip rights review;
- skip factual review;
- skip P26 or P29 gates;
- commit external video assets;
- commit platform credentials or secrets;
- bypass workflow gates.

## Next step

After this PR merges, #357 can design the `produce-longform` command and output contract using this concept model as the planning foundation.
