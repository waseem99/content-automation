# P24 Step 03

This step defines the initial `content_package.json` schema for generated football content runs.

Part of #326. Closes #334 after the PR merges.

## Goal

Define a stable creator-ready manifest contract that every generated run can use as the central handoff point between current production outputs and later YouTube packaging, retention scoring, rights review, platform export, and editorial approval workflows.

## Source references

This schema builds on:

```text
docs/operations/p24-step-01.md
docs/operations/p24-step-02.md
README.md
src/producer.py
src/explainer_producer.py
src/domain/render_status.py
docs/operations/p24-content-package-short-example.json
docs/operations/p24-content-package-explainer-example.json
.github/workflows/p1-acceptance-harness.yml
```

## Schema status

This `content_package.json` schema is documentation and contract focused.

It does not:

- generate final title options;
- generate final first-frame options;
- generate thumbnails;
- score retention automatically;
- score monetization risk automatically;
- clear rights or copyright risk;
- create platform export folders;
- approve editorial status;
- render videos;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Required top-level fields

Every `content_package.json` document must include these top-level fields:

| Field | Type | Purpose |
| --- | --- | --- |
| `schema_version` | string | Version of the package contract. Initial value is `p24.content_package.v1`. |
| `package_id` | string | Stable package identifier for the generated run. |
| `run_identity` | object | Run folder, campaign id, concept id, source command, and created timestamp. |
| `content_type` | string | One of `short`, `explainer`, or future `long_form`. |
| `content_status` | string | Current package state, initially `package_generated` or `draft_contract_example`. |
| `source_assets` | array | Source video, extracted clip, clip pool, manifest, and concept references. |
| `generated_assets` | object | Plans, visuals, audio, captions, rendered outputs, source evidence, and checkpoints. |
| `platform_suitability` | object | Per-platform suitability, missing assets, and review notes. |
| `missing_assets` | array | Creator-ready assets not yet produced. |
| `packaging` | object | P25 placeholders for title options, first-frame options, thumbnail concepts, hook notes, and CTA options. |
| `retention` | object | P25 retention score placeholder and review notes. |
| `rights_and_monetization` | object | P26 placeholders for rights, attribution, originality, and monetization risk. |
| `exports` | object | P27 placeholders for platform-specific export paths. |
| `editorial_review` | object | P29 placeholders for human review status and approval state. |
| `next_actions` | array | Operator-visible next steps before any publish-ready decision. |
| `guardrails` | array | Non-negotiable safety rules attached to the package. |

## Required run_identity fields

`run_identity` must include:

- `run_id`;
- `run_folder`;
- `campaign_id`;
- `concept_id`;
- `source_command`;
- `created_at`;
- `package_owner_role`;
- `reviewer_role`.

Use `null` for fields that do not apply, for example `campaign_id` on a single Short run.

## Required source_assets fields

Each `source_assets` item must include:

- `asset_id`;
- `asset_type`;
- `path`;
- `role`;
- `review_state`;
- `rights_state`;
- `notes`.

Allowed initial `asset_type` values:

- `source_video`;
- `extracted_clip`;
- `clip_pool_manifest`;
- `single_run_manifest`;
- `concept_yaml`;
- `background_music`;
- `external_reference`.

## Required generated_assets sections

`generated_assets` must include these sections even when empty or pending:

- `production_plans`;
- `visuals`;
- `audio`;
- `captions`;
- `rendered_outputs`;
- `source_evidence`;
- `checkpoints`.

Rendered outputs must include:

- `path`;
- `render_mode`;
- `publication_eligible`;
- `review_state`;
- `notes`.

A `preview_video.mp4` entry must always use:

```json
{
  "render_mode": "preview",
  "publication_eligible": false
}
```

## Required platform_suitability fields

`platform_suitability` must include platform objects for:

- `youtube_shorts`;
- `youtube_long_form`;
- `tiktok`;
- `instagram_reels`;
- `facebook_reels`;
- `x_twitter`.

Each platform object must include:

- `status`;
- `usable_current_assets`;
- `missing_assets`;
- `review_requirements`;
- `publish_state`.

Allowed initial platform `status` values:

- `usable_now_review_only`;
- `usable_now_publish_candidate_after_review`;
- `planned_p25`;
- `planned_p26`;
- `planned_p27`;
- `planned_p28`;
- `planned_p29`;
- `not_supported_today`.

## Required missing_assets entries

`missing_assets` should list assets such as:

- `title_options`;
- `first_frame_options`;
- `thumbnail_concepts`;
- `upload_description`;
- `hashtags`;
- `pinned_comment`;
- `retention_score`;
- `hook_score`;
- `cta_comment_trigger_options`;
- `monetization_risk_report`;
- `rights_clearance_status`;
- `originality_assessment`;
- `source_attribution_checklist`;
- `music_license_note`;
- `platform_export_folders`;
- `human_editorial_review_status`;
- `publish_readiness_manifest`.

## Required packaging placeholder

`packaging` must include:

- `title_options`;
- `first_frame_options`;
- `thumbnail_concepts`;
- `hook_notes`;
- `cta_comment_trigger_options`;
- `status`;
- `planned_epic`.

Initial placeholder status should be `pending_p25`.

## Required retention placeholder

`retention` must include:

- `retention_score_path`;
- `hook_score`;
- `first_three_seconds_score`;
- `midpoint_reset_score`;
- `cta_strength_score`;
- `dead_air_risk`;
- `genericness_risk`;
- `recommended_fixes`;
- `status`;
- `planned_epic`.

Initial placeholder status should be `pending_p25`.

## Required rights and monetization placeholder

`rights_and_monetization` must include:

- `monetization_risk_report_path`;
- `publish_allowed`;
- `review_required`;
- `rights_clearance_status`;
- `source_attribution_status`;
- `music_license_status`;
- `originality_status`;
- `blocking_reasons`;
- `required_actions`;
- `status`;
- `planned_epic`.

Initial placeholder status should be `pending_p26`.

`publish_allowed` must default to `false` until later controls prove otherwise.

## Required exports placeholder

`exports` must include:

- `youtube_shorts`;
- `youtube_long_form`;
- `tiktok`;
- `instagram_reels`;
- `facebook_reels`;
- `x_twitter`;
- `status`;
- `planned_epic`.

Initial placeholder status should be `pending_p27`.

Each platform export placeholder must include:

- `export_path`;
- `required_files`;
- `status`;
- `notes`.

## Required editorial review placeholder

`editorial_review` must include:

- `status`;
- `approval_state`;
- `review_owner_role`;
- `rights_reviewer_role`;
- `approved_at`;
- `blockers`;
- `required_actions`;
- `planned_epic`.

Initial approval state should be `not_approved`.

## Required next_actions entries

Each `next_actions` item must include:

- `action_id`;
- `owner_role`;
- `description`;
- `blocking`;
- `target_epic`.

## Extensibility rules

The schema must remain extensible for future long-form support by preserving:

- `content_type: long_form` as a future value;
- `youtube_long_form` inside `platform_suitability`;
- chapter/source-list fields under future production plans;
- thumbnail concepts under `packaging`;
- sponsor slot markers under future generated assets;
- content calendar and series references under future P28 fields.

## Example packages

Example package documents are stored at:

```text
docs/operations/p24-content-package-short-example.json
docs/operations/p24-content-package-explainer-example.json
```

Both examples are contract examples only. They are not publish approvals.

## Stop conditions

Stop schema or package work if:

- `publish_allowed` defaults to `true`;
- `preview_video.mp4` is marked `publication_eligible: true`;
- `image_sources.json` is treated as copyright clearance;
- broadcast footage is treated as rights-cleared by default;
- platform export paths are treated as already generated when P27 has not run;
- editorial approval is implied before P29;
- monetization approval is implied before P26;
- a generated package is described as upload-ready;
- direct platform upload is added;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic rendering.
- No automatic publishing.
- No automatic upload.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic legal approval.
- No automatic platform export.
- No automatic editorial approval.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.

## Validation

Covered by:

```text
tests/integration/test_p24_step_03.py
```

The validation checks schema documentation, example JSON validity, required top-level fields, required package placeholders, platform suitability fields, preview publication blocking, publish-default safety, future long-form extensibility, stop conditions, guardrails, and P24 CI wildcard coverage.
