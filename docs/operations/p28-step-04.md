# P28 Step 04

This step defines the topic scoring and content calendar contract so the team can prioritize football content ideas before spending production time.

Part of #330. Closes #359 after the PR merges.

## Goal

Create a deterministic planning layer for scoring football topics, deciding whether they should be produced, held, researched, or rejected, and placing approved candidates into a review-only content calendar.

## Contract status

This step adds a scoring/calendar contract, example output, and validation coverage only.

It does not:

- scrape live trends;
- call YouTube search-volume APIs;
- schedule content;
- publish content;
- upload to any platform;
- render assets;
- approve rights;
- approve editorial status;
- bypass P26 or P29 gates.

## Topic scoring dimensions

Each topic is scored from 1 to 5 across:

| Dimension | Meaning |
| --- | --- |
| `timeliness` | Current relevance to the football conversation. |
| `search_demand` | Estimated search and evergreen discovery potential without live API data. |
| `emotional_intensity` | Strength of pressure, conflict, nostalgia, shock, or legacy stakes. |
| `comment_potential` | Likelihood that the topic creates healthy debate and comments. |
| `series_fit` | Fit with approved P28 repeatable series formats. |
| `monetization_fit` | Brand safety and long-form monetization suitability. |
| `rights_risk` | Rights, footage, music, source, or claim risk. Lower is better. |
| `production_effort` | Expected research, scripting, design, and editing effort. Lower is better. |

## Recommendation states

The contract supports:

- `produce_now`;
- `hold`;
- `needs_research`;
- `reject_high_risk`.

## Content calendar fields

Each calendar entry must include:

| Field | Purpose |
| --- | --- |
| `publish_window` | Planned publishing window or backlog state. |
| `platform` | Target platform or `none` for rejected topics. |
| `series` | Approved P28 series format. |
| `priority` | High, medium, hold, research, or reject state. |
| `dependencies` | Required work before production or publishing. |
| `review_status` | Review state before production or scheduling. |

## Series connection

Scored topics and calendar entries must connect to approved P28 series formats:

- `Football Pressure Index`;
- `The Moment That Changed`;
- `World Cup What Ifs`;
- `Legacy vs Future`.

## Example output

Example scored topics and calendar output are stored at:

```text
docs/operations/p28-topic-calendar-example.json
```

## Validation

Validation is implemented in:

```text
src/topic_calendar.py
tests/integration/test_p28_step_04.py
```

The validator checks:

- all required scoring dimensions;
- recommendation states;
- scored topic fields;
- score range from 1 to 5;
- approved series connection;
- required content calendar fields;
- dependency lists;
- review status fields;
- live trend scraping remains out of scope;
- YouTube search-volume API integration remains out of scope;
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

- scrape live trends in P28-04;
- call YouTube search-volume APIs in P28-04;
- schedule or publish content;
- upload to platforms;
- render media assets;
- store platform credentials or secrets;
- set `publish_allowed` to `true`;
- bypass rights, factual, source attribution, or editorial review;
- bypass P26 or P29 gates;
- bypass workflow gates.

## Next step

After this PR merges, #360 can define the Shorts-to-long-form funnel and cutdown map using the scoring/calendar contract as planning input.
