# P27 Step 03

This step defines and implements short-form export packs for TikTok, Instagram Reels, and Facebook Reels.

Part of #329. Closes #352 after the PR merges.

## Goal

Create deterministic, human-reviewable short-form export packs for TikTok, Instagram Reels, and Facebook Reels so an operator can review platform-specific captions, hashtags, cover guidance, music-risk notes, and publishing notes before any manual upload.

## Source references

This export pack builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-readiness-report.md
docs/operations/p27-step-01.md
docs/operations/p27-step-02.md
src/cta_library.py
src/visual_concepts.py
src/short_form_exports.py
docs/operations/p27-short-form-export-example.json
tests/integration/test_p27_step_03.py
```

## Contract status

This step adds a deterministic helper and example manifest for three short-form platforms.

It does not:

- render new platform-specific video files;
- commit generated video assets;
- upload to TikTok;
- upload to Meta platforms;
- call TikTok APIs;
- call Meta APIs;
- automate music licensing;
- assume one music license works across platforms;
- approve captions, hashtags, cover frames, rights, monetization, originality, or editorial status;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- bypass workflow gates.

## Supported platforms

| Platform | Directory | Caption style | Required status |
| --- | --- | --- | --- |
| TikTok | `exports/tiktok/` | `fast_hook_direct_question` | Review-only / blocked until review |
| Instagram Reels | `exports/instagram_reels/` | `polished_social_caption` | Review-only / blocked until review |
| Facebook Reels | `exports/facebook_reels/` | `context_first_caption` | Review-only / blocked until review |

Every pack must preserve:

```text
publish_allowed: false
review_required: true
```

## Required files per platform

Each platform export pack must define:

| File | Purpose |
| --- | --- |
| `video.mp4` | Reference to the already-rendered short-form video asset. The helper does not commit or render the video. |
| `caption.txt` | Platform-specific caption text. |
| `hashtags.txt` | Platform-specific hashtag list. |
| `cover_notes.txt` | Cover / first-frame guidance based on the P25 visual concept helper. |
| `music_risk_note.txt` | Music and sound risk note that requires platform-specific review. |
| `publishing_note.txt` | Review-only publishing note with blockers and required actions. |
| `metadata.json` | Machine-readable pack metadata and linkage fields. |
| `review_status.json` | Review gate status that keeps the export blocked until review. |

## Platform differences

The helper must reflect these differences:

- TikTok captions can use a faster direct hook, but must avoid unsupported claims and trend-chasing without rights review.
- Instagram Reels captions should be more polished and grid/share friendly.
- Facebook Reels captions should provide slightly more context before the CTA.
- TikTok cover notes prioritize a strong first-frame hook.
- Instagram cover notes prioritize grid readability and resharing.
- Facebook cover notes prioritize feed preview clarity and context.
- Music and sound rights must be reviewed separately for each platform.

## P25 packaging field mapping

The short-form helper pulls deterministic review candidates from P25 helpers:

| Export file | P25 source |
| --- | --- |
| `caption.txt` | `build_cta_options(...)[0]["cta_text"]` plus platform caption style |
| `cover_notes.txt` | `build_visual_concepts(... )["first_frame_options"][0]` |
| `metadata.json` | selected P25 `cta_id` and `first_frame_concept_id` |

The selected P25 fields remain `not_approved` until human review.

## P26 risk field mapping

The short-form helper accepts an optional P26 publish-block decision. If a decision is not supplied, the helper uses safe defaults.

The export pack must preserve:

- `publish_allowed: false`;
- `review_required: true`;
- P26 monetization and rights review required;
- platform-specific music rights review required;
- P29 editorial approval required;
- visible blocking reasons;
- visible required actions;
- no automatic music clearance;
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
- `caption_style`;
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

The default `export_status` is:

```text
blocked_until_review
```

## Example output

Example output is stored at:

```text
docs/operations/p27-short-form-export-example.json
```

The example includes TikTok, Instagram Reels, and Facebook Reels packs with the required files, selected P25 references, platform-specific caption/cover/music notes, and P26/P29 review defaults.

## Stop conditions

Stop short-form export work if:

- the export pack is treated as platform upload approval;
- `publish_allowed` defaults to `true`;
- P26 publish-block rules are ignored;
- P29 editorial approval is bypassed;
- TikTok or Meta credentials are requested or stored;
- TikTok or Meta API upload is introduced;
- music licensing automation is introduced;
- one music license is assumed to work across all platforms;
- external rendered videos are committed;
- secret values are committed;
- workflow gate bypass is requested.

## Guardrails

- No TikTok upload.
- No Meta upload.
- No platform API integration.
- No platform credentials.
- No music licensing automation.
- No assumption that one music license works across all platforms.
- No external video asset commits.
- No secret values.
- No automatic caption approval.
- No automatic cover approval.
- No automatic music clearance.
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
tests/integration/test_p27_step_03.py
```

The validation checks the documentation, helper output, required file manifests, example output, metadata fields, review status fields, platform differences, music-risk notes, P26/P29 review defaults, stop conditions, guardrails, and deterministic output behavior.
