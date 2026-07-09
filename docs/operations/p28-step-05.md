# P28 Step 05

This step defines the Shorts-to-long-form funnel and cutdown map so Shorts, explainers, and long-form videos connect as a channel funnel instead of disconnected uploads.

Part of #330. Closes #360 after the PR merges.

## Goal

Create a deterministic, review-only funnel contract that maps short-form clips, explainers, long-form videos, and series episodes into connected viewer journeys.

## Contract status

This step adds funnel documentation, a cutdown map example, and validation coverage only.

It does not:

- render Shorts cutdowns;
- render 16:9 video;
- select clips automatically from analytics;
- scrape engagement;
- upload to any platform;
- publish content;
- approve rights;
- approve editorial status;
- bypass P26 or P29 gates.

## Funnel types

The contract supports:

| Funnel type | Purpose |
| --- | --- |
| `short_teaser_to_long_form` | A Short opens a strong curiosity gap and routes viewers to the related long-form episode. |
| `long_form_to_shorts_cutdowns` | A reviewed long-form video produces rights-safe Shorts candidates after editorial review. |
| `explainer_to_debate_short` | A factual explainer becomes a focused debate Short without losing source caveats. |
| `series_episode_to_next_episode_tease` | A series episode end-card becomes a next-episode tease and comment prompt. |

## Cutdown map fields

Each cutdown map entry must include:

| Field | Purpose |
| --- | --- |
| `source_video` | Source long-form or explainer video placeholder/path. |
| `hook_clip` | Specific hook moment or clip description. |
| `cutdown_angle` | Creative angle for the short-form cutdown. |
| `target_platform` | Target platform for the cutdown or funnel asset. |
| `cta` | Call to action for the viewer journey. |
| `linked_long_form_episode` | Related long-form episode identifier. |

The implementation also tracks `map_id`, `format_example`, `funnel_type`, `related_episode_fields`, `series`, `review_status`, `publish_allowed`, and `review_required`.

## Required examples

The example cutdown map includes:

- `football_player_legacy`;
- `world_cup_hype`;
- `match_moment_format`.

## Platform connection

Cutdown maps may target:

- YouTube Shorts;
- TikTok;
- Instagram Reels;
- Facebook Reels;
- X/Twitter;
- YouTube long-form packaging.

All platform packaging remains review-only. P27 export packs may be used only after rights, factual, attribution, monetization, and editorial review.

## Planning connections

The funnel contract connects to:

- `docs/operations/p28-topic-calendar-example.json`;
- `docs/operations/p28-series-metadata-example.json`;
- `docs/operations/p28-produce-longform-output-contract-example.json`;
- `content_package.json`.

## Example output

Example cutdown map output is stored at:

```text
docs/operations/p28-shorts-longform-funnel-example.json
```

## Validation

Validation is implemented in:

```text
src/shorts_longform_funnel.py
tests/integration/test_p28_step_05.py
```

The validator checks:

- required funnel types;
- required cutdown map fields;
- source video field;
- target platform field;
- CTA field;
- linked long-form episode field;
- related episode fields;
- required football example formats;
- P27 export after review connection;
- topic calendar connection;
- series metadata connection;
- produce-longform connection;
- automatic cutdown rendering remains out of scope;
- analytics-based cutdown selection remains out of scope;
- `publish_allowed: false`;
- `review_required: true`.

## Risk and review fields

The contract preserves:

- `rights_review_required: true`;
- `factual_review_required: true`;
- `source_attribution_required: true`;
- `editorial_review_required: true`;
- `publish_allowed: false`;
- `review_required: true`.

## Stop conditions

Stop work if a future change attempts to:

- render Shorts cutdowns in P28-05;
- use analytics-based cutdown selection in P28-05;
- upload to platforms;
- publish content;
- scrape engagement;
- store platform credentials or secrets;
- commit rendered video assets;
- set `publish_allowed` to `true`;
- bypass rights, factual, attribution, monetization, or editorial review;
- bypass P26 or P29 gates;
- bypass workflow gates.

## Next step

After this PR merges, #361 can close out P28 by confirming long-form, series, topic intelligence, and funnel contracts are complete.
