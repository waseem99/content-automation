# P27 Step 02

This step defines and implements the YouTube Shorts export pack for generated football content packages.

Part of #329. Closes #351 after the PR merges.

## Goal

Create a deterministic, human-reviewable YouTube Shorts export pack that gives a publishing operator the metadata needed to manually review a Short without treating the output as upload approval, rights clearance, monetization approval, or publish readiness.

## Source references

This export pack builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-readiness-report.md
docs/operations/p27-step-01.md
docs/operations/p27-export-directory-example.json
src/title_options.py
src/visual_concepts.py
src/cta_library.py
src/youtube_shorts_export.py
docs/operations/p27-youtube-shorts-export-example.json
tests/integration/test_p27_step_02.py
```

## Contract status

This step adds a deterministic helper and example manifest for the YouTube Shorts export pack.

It does not:

- render a new video file;
- commit generated video assets;
- upload to YouTube;
- call the YouTube API;
- connect YouTube Studio analytics;
- approve titles, descriptions, hashtags, CTAs, rights, monetization, originality, or editorial status;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- bypass workflow gates.

## Export directory

The YouTube Shorts export pack uses:

```text
exports/youtube_shorts/
```

The pack remains review-only and must preserve:

```text
publish_allowed: false
review_required: true
```

## Required YouTube Shorts files

The export pack must define these files:

| File | Purpose |
| --- | --- |
| `video.mp4` | Reference to the already-rendered Short video asset. The helper records the source path but does not commit or render the video. |
| `title.txt` | Selected YouTube Shorts title pulled from the P25 title option helper. |
| `description.txt` | Review-safe description text with source package, risk report, and attribution links. |
| `hashtags.txt` | Deterministic hashtag list for review. |
| `pinned_comment.txt` | Selected pinned comment / CTA pulled from the P25 CTA helper. |
| `first_frame_notes.txt` | Selected first-frame concept notes pulled from the P25 visual concept helper. |
| `risk_note.txt` | P26/P29 risk summary, blocking reasons, and required actions. |
| `rights_note.txt` | Rights/source/monetization reminder aligned with P26 guardrails. |
| `metadata.json` | Machine-readable pack metadata and linkage fields. |
| `review_status.json` | Review gate status that keeps the export blocked until review. |

## P25 packaging field mapping

The YouTube Shorts helper pulls deterministic review candidates from P25 helpers:

| Export file | P25 source |
| --- | --- |
| `title.txt` | `build_title_options(...)[0]["title_text"]` |
| `pinned_comment.txt` | `build_cta_options(...)[0]["cta_text"]` |
| `first_frame_notes.txt` | `build_visual_concepts(... )["first_frame_options"][0]` |
| `metadata.json` | selected P25 `title_option_id`, `first_frame_concept_id`, and `cta_id` |

The selected P25 fields remain `not_approved` until human review.

## P26 risk field mapping

The YouTube Shorts helper accepts an optional P26 publish-block decision. If a decision is not supplied, the helper uses safe defaults.

The export pack must preserve:

- `publish_allowed: false`;
- `review_required: true`;
- P26 monetization and rights review required;
- P29 editorial approval required;
- visible blocking reasons;
- visible required actions;
- no automatic rights clearance;
- no automatic monetization approval;
- no automatic editorial approval.

The helper maps P26 fields into:

| Export field/file | P26 source |
| --- | --- |
| `metadata.blocking_reasons` | `publish_block_decision["blocking_reasons"]` or safe defaults |
| `metadata.required_actions` | `publish_block_decision["required_actions"]` or safe defaults |
| `metadata.p26_decision_state` | `publish_block_decision["decision_state"]` or `review_required` |
| `risk_note.txt` | decision state, blocking reasons, required actions, P29 missing status |
| `review_status.json` | required review statuses and blocking reasons |

## Metadata requirements

`metadata.json` must include:

- `schema_version`;
- `package_id`;
- `platform`;
- `export_directory`;
- `content_type`;
- `video_asset_path`;
- `copy_asset_paths`;
- `rights_note_path`;
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
- `music_license_status`;
- `originality_status`;
- `blocking_reasons`;
- `required_actions`;
- `reviewer_role`;
- `notes`.

This export pack is not an upload instruction, rights clearance, monetization approval, or publish approval.

The default `export_status` is:

```text
blocked_until_review
```

## Example output

Example output is stored at:

```text
docs/operations/p27-youtube-shorts-export-example.json
```

The example includes the required YouTube Shorts files, selected P25 packaging references, P26/P29 risk status, metadata, review status, and safe review defaults.

## Operator review checklist

Before a human operator manually prepares a YouTube Short, they must confirm:

- the video asset path is correct;
- the selected title matches the script and does not overstate facts;
- the description includes useful attribution/risk references;
- hashtags are suitable for the target account and content;
- the pinned comment is respectful and aligned with the video;
- first-frame notes match the actual rendered first frame;
- source attribution is complete;
- asset rights and music rights are reviewed;
- monetization and originality risks are reviewed;
- P29 editorial approval is complete.

## Stop conditions

Stop export-pack work if:

- the export pack is treated as upload approval;
- `publish_allowed` defaults to `true`;
- P26 publish-block rules are ignored;
- P29 editorial approval is bypassed;
- YouTube credentials are requested or stored;
- YouTube API upload is introduced;
- external rendered videos are committed;
- secret values are committed;
- workflow gate bypass is requested.

## Guardrails

- No YouTube API upload.
- No platform publishing.
- No YouTube Studio analytics integration.
- No platform credentials.
- No external video asset commits.
- No secret values.
- No automatic title approval.
- No automatic description approval.
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
tests/integration/test_p27_step_02.py
```

The validation checks the documentation, helper output, required file manifest, example output, metadata fields, review status fields, P25 mappings, P26/P29 review defaults, stop conditions, guardrails, and deterministic output behavior.
