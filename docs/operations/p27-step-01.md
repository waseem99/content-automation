# P27 Step 01

This step defines the platform export directory contract for generated football content packages.

Part of #329. Closes #350 after the PR merges.

## Goal

Define a stable export folder structure and metadata contract for YouTube Shorts, YouTube long-form, TikTok, Instagram Reels, Facebook Reels, and X/Twitter so future P27 tasks can generate platform-specific export packs without treating any output as automatically publish-ready.

## Source references

This export directory contract builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-readiness-report.md
docs/operations/p24-step-02.md
docs/operations/p26-step-05.md
src/content_package.py
docs/operations/p27-export-directory-example.json
tests/integration/test_p27_step_01.py
.github/workflows/p1-acceptance-harness.yml
```

## Contract status

This step is documentation and contract focused.

It does not:

- generate export packs;
- render new videos;
- upload to platforms;
- publish content;
- approve monetization;
- approve rights;
- approve editorial status;
- bypass P26 publish-block rules;
- bypass P29 editorial approval;
- bypass workflow gates.

## Required root export directory

All platform export packs must live under:

```text
exports/
```

Required platform directories:

```text
exports/youtube_shorts/
exports/youtube_longform/
exports/tiktok/
exports/instagram_reels/
exports/facebook_reels/
exports/x_twitter/
```

## Required shared export files

Every platform export directory should eventually support these shared files where applicable:

- `video.mp4`;
- `metadata.json`;
- `caption.txt`;
- `hashtags.txt`;
- `rights_note.txt`;
- `review_status.json`.

A platform directory may omit files that are not relevant to that platform, but omission must be documented in `metadata.json`.

## Platform-specific export file contract

| Platform | Directory | Required future files | Status |
| --- | --- | --- | --- |
| YouTube Shorts | `exports/youtube_shorts/` | `video.mp4`, `title.txt`, `description.txt`, `hashtags.txt`, `pinned_comment.txt`, `rights_note.txt`, `review_status.json` | Contract only in this step. |
| YouTube long-form | `exports/youtube_longform/` | `video.mp4`, `title.txt`, `description.txt`, `thumbnail_brief.md`, `chapters.txt`, `source_list.txt`, `rights_note.txt`, `review_status.json` | Contract only in this step. |
| TikTok | `exports/tiktok/` | `video.mp4`, `caption.txt`, `hashtags.txt`, `music_rights_note.txt`, `cover_note.txt`, `review_status.json` | Contract only in this step. |
| Instagram Reels | `exports/instagram_reels/` | `video.mp4`, `caption.txt`, `hashtags.txt`, `cover_frame_note.txt`, `collaborator_tags.txt`, `rights_note.txt`, `review_status.json` | Contract only in this step. |
| Facebook Reels | `exports/facebook_reels/` | `video.mp4`, `caption.txt`, `hashtags.txt`, `monetization_note.txt`, `rights_note.txt`, `review_status.json` | Contract only in this step. |
| X/Twitter | `exports/x_twitter/` | `video.mp4`, `post_copy.txt`, `thread_outline.txt`, `hashtags.txt`, `rights_note.txt`, `review_status.json` | Contract only in this step. |

## metadata.json required fields

Each future platform `metadata.json` must include:

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
- `planned_epic`.

## review_status.json required fields

Each future platform `review_status.json` must include:

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

Allowed `export_status` values:

- `contract_only`;
- `not_started`;
- `generated_pending_review`;
- `blocked_until_review`;
- `export_candidate_after_review`.

`export_candidate_after_review` must not imply publish approval.

## Platform naming rules

Allowed platform identifiers:

- `youtube_shorts`;
- `youtube_longform`;
- `tiktok`;
- `instagram_reels`;
- `facebook_reels`;
- `x_twitter`.

Do not use inconsistent names such as:

- `youtube-long-form`;
- `youtube_long_form`;
- `twitter`;
- `x`;
- `ig_reels`;
- `fb_reels`.

## Package linkage requirements

Every export pack must link back to:

- the P24 `content_package.json`;
- the P25 packaging fields;
- the P25 retention fields;
- the P26 `monetization_risk_report.json`;
- the P26 source attribution records;
- the P26 publish-block decision;
- the future P29 editorial review status.

## P26 safety requirements

Every export directory must preserve these defaults until P29 changes them:

- `publish_allowed: false`;
- `review_required: true`;
- P26 rights and monetization review required;
- P29 editorial review required;
- unresolved hard blockers remain visible;
- export files are not upload instructions;
- export files are not publish approval.

## Expected future directory tree

```text
exports/
├── youtube_shorts/
│   ├── video.mp4
│   ├── title.txt
│   ├── description.txt
│   ├── hashtags.txt
│   ├── pinned_comment.txt
│   ├── rights_note.txt
│   ├── metadata.json
│   └── review_status.json
├── youtube_longform/
│   ├── video.mp4
│   ├── title.txt
│   ├── description.txt
│   ├── thumbnail_brief.md
│   ├── chapters.txt
│   ├── source_list.txt
│   ├── rights_note.txt
│   ├── metadata.json
│   └── review_status.json
├── tiktok/
│   ├── video.mp4
│   ├── caption.txt
│   ├── hashtags.txt
│   ├── music_rights_note.txt
│   ├── cover_note.txt
│   ├── metadata.json
│   └── review_status.json
├── instagram_reels/
│   ├── video.mp4
│   ├── caption.txt
│   ├── hashtags.txt
│   ├── cover_frame_note.txt
│   ├── collaborator_tags.txt
│   ├── rights_note.txt
│   ├── metadata.json
│   └── review_status.json
├── facebook_reels/
│   ├── video.mp4
│   ├── caption.txt
│   ├── hashtags.txt
│   ├── monetization_note.txt
│   ├── rights_note.txt
│   ├── metadata.json
│   └── review_status.json
└── x_twitter/
    ├── video.mp4
    ├── post_copy.txt
    ├── thread_outline.txt
    ├── hashtags.txt
    ├── rights_note.txt
    ├── metadata.json
    └── review_status.json
```

## Example contract output

Example export directory metadata is stored at:

```text
docs/operations/p27-export-directory-example.json
```

The example includes all six platform directories with required file lists, metadata fields, and review defaults.

## Downstream task mapping

- P27-02 should generate the YouTube Shorts export pack.
- P27-03 should generate TikTok, Instagram Reels, and Facebook Reels export packs.
- P27-04 should generate X/Twitter caption and thread export pack.
- P27-05 should validate cross-platform export readiness.
- P27-06 should close P27 with readiness evidence.

## Stop conditions

Stop export contract work if:

- an export directory is treated as upload approval;
- `publish_allowed` defaults to `true`;
- P26 publish-block rules are ignored;
- P29 editorial approval is bypassed;
- platform credentials are requested or stored;
- platform APIs are introduced;
- external exports are committed;
- secret values are committed;
- workflow gate bypass is requested.

## Guardrails

- No platform upload.
- No platform publishing.
- No platform API integration.
- No platform credentials.
- No external package exports.
- No secret values.
- No automatic publish approval.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic editorial approval.
- No bypass of P26 publish-block rules.
- No bypass of P29 editorial governance.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p27_step_01.py
```

The validation checks required directories, shared files, platform-specific file contracts, metadata fields, review status fields, allowed platform identifiers, package linkage, P26 safety requirements, example output, downstream task mapping, stop conditions, guardrails, and P27 CI wildcard coverage.
