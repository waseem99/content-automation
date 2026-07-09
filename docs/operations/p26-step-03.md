# P26 Step 03

This step defines source attribution and license tracking requirements for generated football content packages.

Part of #328. Closes #346 after the PR merges.

## Goal

Strengthen source and attribution tracking for web images, stats, music, source clips, AI visuals, and packaging claims so operators can review license, attribution, factual, and platform-use requirements before any export or publish-ready decision.

## Source references

This attribution and license tracking model builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-step-01.md
docs/operations/p26-step-02.md
src/content_package.py
docs/operations/p26-source-attribution-example.json
tests/integration/test_p26_step_03.py
.github/workflows/p1-acceptance-harness.yml
```

## Tracking status

This attribution model is documentation and contract focused.

It does not:

- verify licenses automatically;
- fetch source pages automatically;
- provide legal advice;
- clear copyrights;
- approve attribution sufficiency;
- approve monetization;
- approve publishing;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Required attribution fields

Every source or attribution record must include:

| Field | Purpose |
| --- | --- |
| `record_id` | Stable attribution record identifier. |
| `asset_id` | Asset identifier used in package or risk report. |
| `asset_role` | Asset role such as `web_image`, `stat`, `music`, `source_clip`, `ai_image`, `title_option`, or `cta_option`. |
| `asset_path` | Local asset path or package field path when applicable. |
| `source_url` | Original source URL when available. |
| `source_domain` | Domain extracted or recorded from the source URL. |
| `source_title` | Human-readable source title, page title, asset name, or provider name. |
| `license_or_filter_pass` | License name, usage summary, provider terms, or filter used during discovery. |
| `checked_at` | Timestamp or date when the operator checked the source/license information. |
| `checked_by_role` | Role that checked the source, such as `content operator` or `rights reviewer`. |
| `attribution_needed` | Whether attribution appears required, unknown, or not required. |
| `attribution_text` | Attribution text to use if required or recommended. |
| `attribution_placement` | Where attribution should appear, such as `youtube_description`, `internal_evidence_only`, or `not_applicable`. |
| `commercial_use_status` | Whether commercial/social/video use appears allowed, disallowed, unknown, or not applicable. |
| `platform_use_status` | Whether use appears allowed for YouTube, TikTok, Instagram, Facebook, or X/Twitter. |
| `review_status` | Current review state. |
| `risk_level` | Risk label aligned with P26-01 and P26-02. |
| `blocking_reasons` | Blocking reasons if publish-readiness is not allowed. |
| `required_actions` | Required actions before export or publish-ready state. |
| `evidence_allowed` | Safe evidence fields that may be stored in the repo. |
| `evidence_blocked` | Private evidence that must not be committed. |
| `notes` | Non-sensitive operator notes. |

## Allowed review statuses

Allowed `review_status` values:

- `not_started`;
- `source_recorded`;
- `license_review_required`;
- `attribution_required`;
- `attribution_not_required`;
- `blocked_until_review`;
- `rejected_replace_asset`;
- `reviewed_for_internal_use_only`;
- `reviewed_pending_editorial`;
- `reviewed_for_export_candidate`.

`reviewed_for_export_candidate` does not mean publish approval.

## Required asset coverage

Attribution and source tracking must cover:

- `web_image`;
- `ai_image`;
- `stat`;
- `music`;
- `source_clip`;
- `broadcast_clip`;
- `extracted_clip`;
- `voiceover`;
- `title_option`;
- `thumbnail_concept`;
- `first_frame_option`;
- `cta_option`;
- `concept_yaml_claim`;
- `caption_claim`;
- `production_plan_claim`.

## image_sources.json usage

`image_sources.json` must be treated as source evidence only.

It may store:

- image path;
- source URL;
- source domain;
- source title;
- provider or discovery source;
- license/filter pass summary;
- attribution-needed status;
- checked date;
- review status;
- non-sensitive notes.

It must not be treated as:

- copyright clearance;
- legal approval;
- monetization approval;
- platform approval;
- proof that commercial use is allowed;
- proof that attribution is complete;
- proof that a player likeness, logo, or trademark is safe.

## Web image tracking requirements

For every web image, record:

- source URL;
- source domain;
- source title;
- local image path;
- provider or discovery source;
- license/filter pass;
- commercial use status;
- attribution-needed status;
- attribution text if needed;
- checked date;
- review status;
- risk level;
- required actions.

Default review state should be `license_review_required` unless the source was reviewed by a rights reviewer.

## Stats and concept YAML requirements

Future concept YAML stats should include source references.

Each stat or claim should include:

- `claim_id`;
- `claim_text`;
- `metric_name`;
- `metric_value`;
- `source_url`;
- `source_domain`;
- `source_title`;
- `checked_at`;
- `checked_by_role`;
- `review_status`;
- `notes`.

Stats must remain blocked if the source is missing, unclear, outdated, or mismatched with the claim.

## Music tracking requirements

For every music or sound asset, record:

- source URL or provider name;
- track title;
- artist or provider when known;
- license summary;
- platform coverage;
- commercial use status;
- attribution-needed status;
- checked date;
- review status;
- blocking reasons;
- required actions.

Music must remain blocked if YouTube, TikTok, Instagram, Facebook, and X/Twitter usage is not clearly covered for the intended export.

## Source clip tracking requirements

For every source clip, broadcast clip, or extracted clip, record:

- source video path or URL;
- original owner or provider when known;
- clip path;
- clip duration;
- timestamp range;
- source match or event context;
- commentary/analysis layer status;
- license or permission status;
- platform-use status;
- review status;
- blocking reasons;
- required actions.

Broadcast footage and extracted clips must default to `blocked_until_review`.

## Attribution placement options

Allowed `attribution_placement` values:

- `youtube_description`;
- `video_end_card`;
- `on_screen_caption`;
- `platform_caption`;
- `internal_evidence_only`;
- `not_applicable`;
- `blocked_until_review`.

Use `internal_evidence_only` only when attribution is not required externally but the operator still needs lineage evidence.

Use `blocked_until_review` when attribution requirements are unknown or unresolved.

## Example attribution records

Example source and attribution records are stored at:

```text
docs/operations/p26-source-attribution-example.json
```

The example includes records for:

- a web image;
- a football stat;
- a music asset;
- an extracted clip;
- an AI visual;
- a title option.

## content_package.json linkage

Attribution records should link back to the P24 package through:

- `package_id`;
- `asset_id`;
- `asset_path`;
- `source_assets` entries;
- `generated_assets.source_evidence`;
- `rights_and_monetization.source_attribution_status`;
- `rights_and_monetization.required_actions`.

Attribution tracking can update package status to `source_attribution_review_required` or `source_attribution_blocked`, but it must not set `publish_allowed` to `true`.

## monetization_risk_report.json linkage

Attribution records should feed P26 risk reports through:

- `asset_risks`;
- `image_license_risk`;
- `music_license_risk`;
- `copyright_risk`;
- `factual_risk`;
- `blocking_reasons`;
- `required_actions`;
- `evidence_allowed`;
- `evidence_blocked`.

## Evidence allowed in repository

Allowed evidence:

- source URL;
- source domain;
- source title;
- local asset path;
- license summary;
- attribution-needed status;
- attribution text;
- checked date;
- reviewer role;
- review status;
- non-sensitive notes;
- PR or issue reference.

## Evidence blocked from repository

Do not commit:

- private license documents;
- private account screenshots;
- account IDs not already public;
- private creator agreements;
- private customer data;
- raw legal correspondence;
- secret values;
- tokens;
- private runtime values;
- unredacted invoices;
- external package exports.

## Stop conditions

Stop attribution work if:

- `image_sources.json` is treated as copyright clearance;
- a source URL is treated as license approval;
- missing attribution is ignored;
- missing stat sources are allowed for publish-readiness;
- music platform coverage is assumed;
- broadcast clips are treated as rights-cleared by default;
- `reviewed_for_export_candidate` is treated as publish approval;
- `publish_allowed` is changed to `true`;
- upload or publishing is introduced;
- legal clearance is implied;
- monetization approval is implied;
- workflow gate bypass is requested.

## Guardrails

- No automated license verification.
- No automated legal clearance.
- No copyright claim prediction.
- No Content ID prediction.
- No automatic attribution approval.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic publishing approval.
- No automatic upload.
- No automatic publishing.
- No platform API enforcement.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p26_step_03.py
```

The validation checks required attribution fields, allowed review statuses, required asset coverage, `image_sources.json` limits, web image requirements, concept YAML stat requirements, music requirements, source clip requirements, attribution placement options, example records, package/risk-report linkage, stop conditions, guardrails, and P26 CI wildcard coverage.
