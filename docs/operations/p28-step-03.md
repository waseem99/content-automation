# P28 Step 03

This step adds a series and episode metadata contract so the repo can support repeatable football content formats instead of one-off videos only.

Part of #330. Closes #358 after the PR merges.

## Goal

Define reusable series metadata for football formats that can connect long-form planning, related Shorts, content package output, and future packaging workflows.

## Contract status

This step adds a metadata contract, example catalog, and validation coverage only.

It does not:

- implement a full channel CMS;
- schedule videos;
- publish videos;
- upload to any platform;
- render video assets;
- ingest analytics;
- approve rights;
- approve editorial status;
- bypass P26 or P29 gates.

## Required series fields

Each series metadata entry includes:

| Field | Purpose |
| --- | --- |
| `series_name` | Human-readable repeatable format name. |
| `series_slug` | Stable slug for folder, metadata, and references. |
| `episode_number` | Episode number within the series. |
| `recurring_question` | Repeatable question every episode answers. |
| `format_promise` | Promise that makes the series recognizable. |
| `target_audience` | Viewer segment for the series. |
| `emotional_trigger` | Emotional hook that drives repeat viewing. |
| `next_episode_tease` | Forward-looking teaser for the next episode. |
| `related_shorts` | Shorts cutdown ideas connected to long-form sections. |
| `packaging_connection` | Link to produce-longform and future platform packaging. |
| `content_package_connection` | Link back to `content_package.json`. |
| `publish_allowed` | Always `false` at this step. |
| `review_required` | Always `true` at this step. |

## Required example formats

The example catalog includes four repeatable football series formats:

1. `Football Pressure Index`
2. `The Moment That Changed`
3. `World Cup What Ifs`
4. `Legacy vs Future`

At least three repeatable formats are required by #358; this step includes four to cover the full requested set.

## Related Shorts

Each series includes related Shorts metadata with:

- `short_type`;
- `source_section`;
- `hook`;
- `p27_export_after_review`.

Related Shorts are not automatically exported or published. They only identify candidate cutdowns that may use P27 export packs after review.

## Content package connection

Series metadata enriches `content_package.json` without replacing it.

Each series includes:

- `content_package_path`;
- `series_metadata_path`;
- relationship notes for the content package bridge.

## Packaging connection

Each series links to the P28 `produce-longform` output contract and future platform packaging through:

- `produce_longform_contract_path`;
- future YouTube long-form packaging status;
- P27 related Shorts export status after review;
- direct publishing out-of-scope status.

## Risk and review fields

The catalog preserves:

- `rights_review_required: true`;
- `factual_review_required: true`;
- `source_attribution_required: true`;
- `editorial_review_required: true`;
- `publish_allowed: false`;
- `review_required: true`.

## Example output

Example series metadata output is stored at:

```text
docs/operations/p28-series-metadata-example.json
```

## Validation

Validation is implemented in:

```text
src/series_metadata.py
tests/integration/test_p28_step_03.py
```

The validator checks:

- required catalog schema;
- at least three series formats;
- required example series names;
- required series fields;
- recurring question;
- next episode tease;
- related Shorts fields;
- content package connection;
- produce-longform packaging connection;
- P27 export-after-review connection;
- scheduling and publishing automation out-of-scope flags;
- review-only defaults.

## Stop conditions

Stop work if a future change attempts to:

- implement a full channel CMS in P28-03;
- schedule or publish content;
- upload to platforms;
- commit rendered video assets;
- store platform credentials or secrets;
- set `publish_allowed` to `true`;
- bypass rights, factual, source attribution, or editorial review;
- bypass P26 or P29 gates;
- bypass workflow gates.

## Next step

After this PR merges, #359 can define topic scoring and content calendar contracts using these repeatable series formats.
