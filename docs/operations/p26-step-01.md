# P26 Step 01

This step defines the asset rights classification model for football content packages.

Part of #328. Closes #344 after the PR merges.

## Goal

Define default rights and monetization-risk classification for every major asset type used in generated videos so operators can quickly see which assets are low, medium, high, or blocked until human review before publishing.

## Source references

This classification model builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p24-step-03.md
src/content_package.py
src/title_options.py
src/visual_concepts.py
src/retention_score.py
src/cta_library.py
.github/workflows/p1-acceptance-harness.yml
```

## Classification status

This rights classification model is documentation-only.

It does not:

- clear copyrights;
- provide legal advice;
- predict Content ID claims;
- predict copyright strikes;
- verify licenses automatically;
- fetch license pages;
- inspect private platform accounts;
- approve monetization;
- approve publishing;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Risk levels

Use these risk levels for package assets:

| Risk level | Meaning |
| --- | --- |
| `low` | Low expected risk, but still subject to normal review and evidence checks. |
| `medium` | Requires human review and source/usage confirmation before publish-readiness. |
| `high` | Must be treated as blocked until rights, attribution, or use-case review is complete. |
| `blocked_until_review` | Cannot be included in a publish-ready package until a named reviewer clears or replaces it. |
| `not_applicable` | Rights review is not applicable, but factual or editorial review may still be needed. |

## Required asset roles

Every rights classification item must define:

- `asset_role`;
- `default_risk_level`;
- `review_action`;
- `allowed_evidence`;
- `blocked_evidence`;
- `publish_blocking_by_default`;
- `notes`.

## Asset classification matrix

| Asset role | Default risk level | Publish-blocking by default | Required human review action |
| --- | --- | --- | --- |
| `source_video` | `high` | yes | Confirm ownership, license, permission, source, and platform use rights. |
| `broadcast_clip` | `blocked_until_review` | yes | Treat football broadcast footage as not rights-cleared unless explicit rights or legal/editorial clearance exists. |
| `extracted_clip` | `blocked_until_review` | yes | Review source footage rights, clip duration, transformative use, commentary layer, and platform risk. |
| `web_image` | `medium` | yes | Verify source URL, license, attribution needs, image subject, and allowed commercial/platform use. |
| `ai_image` | `medium` | yes | Review likeness, logo, trademark, prompt, provenance, and whether it implies a real player or event falsely. |
| `voiceover` | `low` | no | Confirm voice provider license and approved usage terms. |
| `music` | `high` | yes | Confirm music license per platform; do not assume one license covers YouTube, TikTok, Instagram, Facebook, and X/Twitter. |
| `font` | `medium` | yes | Confirm font license for video/commercial/social usage. |
| `logo` | `high` | yes | Confirm rights to use club, league, tournament, sponsor, platform, or brand marks. |
| `overlay` | `medium` | yes | Review whether overlays include logos, photos, third-party art, maps, or copied graphics. |
| `script` | `medium` | yes | Review factual support, originality, defamation, harassment, and source claims. |
| `stat` | `medium` | yes | Verify source, date checked, metric definition, and factual accuracy. |
| `concept_yaml` | `medium` | yes | Review claims, stats, player descriptions, and source references. |
| `manifest` | `not_applicable` | no | Use as lineage evidence only; do not treat it as rights clearance. |
| `production_plan` | `medium` | yes | Review narration, visual beats, search queries, claims, and implied rights. |
| `caption_file` | `medium` | yes | Review captions for factual claims, slurs, harassment, and mismatched transcription. |
| `thumbnail_concept` | `medium` | yes | Review suggested text, visual claim, player likeness, logos, and image rights. |
| `title_option` | `medium` | yes | Review clickbait, unsupported claims, and factual alignment with script/source evidence. |
| `cta_option` | `medium` | yes | Review for harassment, inflammatory wording, abuse-baiting, and unsupported claims. |
| `retention_score_report` | `not_applicable` | no | Use as packaging evidence only; it does not approve rights, monetization, or publishing. |

## Evidence allowed in repository

Allowed evidence:

- asset role;
- asset path;
- source URL;
- source domain;
- license name or summary;
- attribution-needed status;
- reviewer role;
- review status;
- non-sensitive decision summary;
- issue or PR reference;
- CI run identifier;
- merge commit reference.

## Evidence blocked from repository

Do not commit:

- paid license documents containing private account data;
- private account screenshots;
- platform account IDs not already public;
- private creator contracts;
- private customer data;
- raw legal correspondence;
- secret values;
- tokens;
- private runtime values;
- unredacted invoices;
- external package exports.

## Required examples

### Football match footage

Football match footage, broadcast highlights, extracted clips, and match stills must default to `blocked_until_review`.

Required action:

- confirm source ownership or permission;
- confirm whether use is allowed on the target platform;
- confirm whether commentary, analysis, or transformation is sufficient for the intended review policy;
- confirm duration and context;
- confirm whether replacement, removal, or private-review-only status is needed.

### Wikimedia images

Wikimedia images may vary by license and must default to `medium` until checked.

Required action:

- verify the exact license page;
- capture attribution requirements;
- confirm commercial/social/video use is allowed;
- confirm the image subject is represented accurately;
- record source URL and checked date.

### Pexels and Pixabay images

Pexels and Pixabay images may be lower risk than unfiltered web images, but they still require review.

Required action:

- verify the asset source page;
- confirm the license terms;
- confirm no trademark, logo, or identifiable person issue remains;
- record source URL and checked date.

### AI visuals

AI visuals default to `medium` and remain publish-blocking until reviewed.

Required action:

- confirm the prompt does not create a false real-world event;
- confirm the image does not misuse player likeness;
- confirm no club, league, sponsor, or tournament logo is generated without review;
- confirm the image is not presented as real footage.

### Background music

Background music defaults to `high` and publish-blocking.

Required action:

- verify the license source;
- verify target platform coverage;
- verify commercial/social use rights;
- confirm whether attribution is required;
- keep music blocked if a platform-specific license cannot be confirmed.

## Connection to future risk report

P26-02 should use this classification model to populate `monetization_risk_report.json` fields for:

- `asset_role`;
- `default_risk_level`;
- `review_required`;
- `publish_blocking_by_default`;
- `required_actions`;
- `blocking_reasons`;
- `evidence_allowed`;
- `evidence_blocked`.

## Stop conditions

Stop rights classification work if:

- broadcast clips are marked low risk by default;
- extracted clips are marked rights-cleared by default;
- unverified music is marked low risk by default;
- web image filtering is treated as legal clearance;
- `image_sources.json` is treated as copyright clearance;
- a retention score is treated as rights clearance;
- platform upload is introduced;
- monetization approval is implied;
- legal approval is implied;
- workflow gate bypass is requested.

## Guardrails

- No automated legal clearance.
- No copyright claim prediction.
- No Content ID prediction.
- No automatic license verification.
- No automatic rights clearance.
- No automatic monetization approval.
- No automatic publishing approval.
- No automatic upload.
- No automatic publishing.
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
tests/integration/test_p26_step_01.py
```

The validation checks required asset roles, default risk levels, review actions, football match footage, Wikimedia/Pexels/Pixabay examples, AI visual handling, background music handling, future risk-report linkage, stop conditions, guardrails, and P26 CI wildcard coverage.
