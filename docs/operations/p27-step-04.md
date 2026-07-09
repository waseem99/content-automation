# P27 Step 04

This step defines and implements the X/Twitter caption and thread export pack for generated football content packages.

Part of #329. Closes #353 after the PR merges.

## Goal

Create a deterministic, human-reviewable X/Twitter export pack that turns a generated football video into a short post, optional thread, hashtags, debate prompt, and risk note.

## Source references

This export pack builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-readiness-report.md
docs/operations/p27-step-01.md
docs/operations/p27-step-02.md
docs/operations/p27-step-03.md
src/cta_library.py
src/x_twitter_export.py
docs/operations/p27-x-twitter-export-example.json
tests/integration/test_p27_step_04.py
```

## Contract status

This step adds a deterministic helper and example manifest for X/Twitter copy export.

It does not:

- post through the X API;
- scrape replies;
- scrape engagement data;
- collect analytics;
- render a new video file;
- commit generated video assets;
- approve facts, stats, rights, monetization, originality, or editorial status;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- bypass workflow gates.

## Export directory

The X/Twitter export pack uses:

```text
exports/x_twitter/
```

The pack remains review-only and must preserve:

```text
publish_allowed: false
review_required: true
```

## Required X/Twitter files

The export pack must define these files:

| File | Purpose |
| --- | --- |
| `video.mp4` | Reference to the already-rendered video asset. The helper records the source path but does not commit or render the video. |
| `post.txt` | Concise short post, capped to 280 characters. |
| `thread.txt` | Optional thread summary, especially useful for explainers. |
| `hashtags.txt` | Deterministic football hashtag list for review. |
| `debate_prompt.txt` | Debate-oriented prompt pulled from the P25 CTA helper. |
| `risk_note.txt` | Factual, source, rights, P26, and P29 risk summary. |
| `metadata.json` | Machine-readable pack metadata and linkage fields. |
| `review_status.json` | Review gate status that keeps the export blocked until review. |

## Copy rules

X/Twitter copy must stay:

- short;
- specific;
- debate-oriented;
- grounded in the video topic;
- free of unsupported stats or claims;
- free of scraped reply or engagement assumptions.

The post must stay within the 280-character limit. Thread output is available for explainers and can also be reviewed for Shorts.

## P25 packaging field mapping

The X/Twitter helper pulls deterministic review candidates from P25 helpers:

| Export file | P25 source |
| --- | --- |
| `post.txt` | `build_cta_options(...)[0]["cta_text"]` combined with the subject |
| `debate_prompt.txt` | `build_cta_options(...)[0]["cta_text"]` |
| `metadata.json` | selected P25 `cta_id` |

The selected P25 fields remain `not_approved` until human review.

## P26 risk field mapping

The X/Twitter helper accepts an optional P26 publish-block decision. If a decision is not supplied, the helper uses safe defaults.

The export pack must preserve:

- `publish_allowed: false`;
- `review_required: true`;
- factual/stat review required;
- P26 rights and monetization review required;
- P29 editorial approval required;
- visible blocking reasons;
- visible required actions;
- no automatic rights clearance;
- no automatic monetization approval;
- no automatic editorial approval.

## Metadata requirements

`metadata.json` must include:

- `schema_version`;
- `package_id`;
- `platform`;
- `export_directory`;
- `content_type`;
- `video_asset_path`;
- `copy_asset_paths`;
- `review_status_path`;
- `source_package_path`;
- `monetization_risk_report_path`;
- `source_attribution_path`;
- `publish_allowed`;
- `review_required`;
- `blocking_reasons`;
- `required_actions`;
- `created_by_step`;
- `planned_epic`;
- `copy_constraints`;
- `p25_packaging_sources`;
- `p26_decision_state`.

## Review status requirements

`review_status.json` must include:

- `platform`;
- `package_id`;
- `export_status`;
- `publish_allowed`;
- `p26_review_status`;
- `p29_editorial_status`;
- `rights_status`;
- `monetization_status`;
- `source_attribution_status`;
- `factual_status`;
- `originality_status`;
- `blocking_reasons`;
- `required_actions`;
- `reviewer_role`;
- `notes`.

The default `export_status` is:

```text
blocked_until_review
```

## Example output

Example output is stored at:

```text
docs/operations/p27-x-twitter-export-example.json
```

The example includes post, optional thread, hashtags, debate prompt, risk note, selected P25 reference, and P26/P29 review defaults.

## Stop conditions

Stop X/Twitter export work if:

- the export pack is treated as post approval;
- `publish_allowed` defaults to `true`;
- P26 publish-block rules are ignored;
- P29 editorial approval is bypassed;
- X API credentials are requested or stored;
- X API posting is introduced;
- scraping replies or engagement data is introduced;
- stats or factual claims are treated as verified without review;
- external rendered videos are committed;
- secret values are committed;
- workflow gate bypass is requested.

## Guardrails

- No X API posting.
- No reply scraping.
- No engagement-data scraping.
- No platform credentials.
- No external video asset commits.
- No secret values.
- No automatic post approval.
- No automatic thread approval.
- No automatic factual/stat approval.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic editorial approval.
- No bypass of P26 publish-block rules.
- No bypass of P29 editorial governance.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p27_step_04.py
```

The validation checks the documentation, helper output, required file manifest, example output, metadata fields, review status fields, short/debate-oriented copy, explainer thread support, risk caveats, P26/P29 review defaults, stop conditions, guardrails, and deterministic output behavior.
