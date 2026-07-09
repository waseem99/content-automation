# P26 Step 04

This step defines originality layer requirements for generated football content packages.

Part of #328. Closes #347 after the PR merges.

## Goal

Define what makes each generated football video meaningfully original enough to reduce reused-content, repetitive automation, low-effort compilation, and generic-template risk before platform export or publish-ready review.

## Source references

This originality model builds on:

```text
docs/operations/p24-readiness-report.md
docs/operations/p25-readiness-report.md
docs/operations/p26-step-01.md
docs/operations/p26-step-02.md
docs/operations/p26-step-03.md
src/content_package.py
docs/operations/p26-originality-layer-example.json
tests/integration/test_p26_step_04.py
.github/workflows/p1-acceptance-harness.yml
```

## Originality status

This originality model is documentation and contract focused.

It does not:

- rewrite videos automatically;
- create a full creative rewrite engine;
- generate a human host or avatar;
- approve monetization;
- approve rights;
- approve publishing;
- clear reused-content risk automatically;
- upload to any platform;
- publish content;
- bypass workflow gates.

## Required originality signals

A package should include multiple originality signals before it can be considered for publish-ready review.

Required signal types:

- `unique_narration_angle`;
- `original_analysis`;
- `custom_stat_card`;
- `sourced_comparison`;
- `human_editorial_view`;
- `custom_graphic_or_visual_structure`;
- `host_or_avatar_layer`;
- `contextual_timeline`;
- `counterpoint_or_nuance`;
- `original_cta_or_debate_frame`.

## Originality signal schema

Each originality signal must include:

- `signal_id`;
- `signal_type`;
- `description`;
- `evidence_path`;
- `source_reference`;
- `strength`;
- `review_required`;
- `review_status`;
- `notes`.

Allowed `strength` values:

- `weak`;
- `moderate`;
- `strong`.

Allowed `review_status` values:

- `not_started`;
- `drafted`;
- `review_required`;
- `revision_required`;
- `reviewed_pending_editorial`;
- `approved_for_editorial_review`.

`approved_for_editorial_review` does not mean publish approval.

## Minimum originality requirements for Shorts

A Short must include at least three originality signals before export candidate review:

1. one `unique_narration_angle` or `original_analysis` signal;
2. one `custom_stat_card`, `sourced_comparison`, `contextual_timeline`, or `custom_graphic_or_visual_structure` signal;
3. one `original_cta_or_debate_frame`, `counterpoint_or_nuance`, or `human_editorial_view` signal.

A Short should be blocked if it is only:

- a raw clip;
- a clip montage;
- a generic AI voiceover;
- a slideshow of web images;
- a copied headline with captions;
- a template with swapped player names.

## Minimum originality requirements for explainers

An explainer must include at least five originality signals before export candidate review:

1. one `unique_narration_angle` signal;
2. one `original_analysis` signal;
3. one `sourced_comparison` or `custom_stat_card` signal;
4. one `contextual_timeline` or `counterpoint_or_nuance` signal;
5. one `custom_graphic_or_visual_structure`, `human_editorial_view`, or `host_or_avatar_layer` signal.

An explainer should be blocked if it is only:

- a listicle with no original framing;
- generic facts read over stock images;
- repeated template sections for each player;
- copied rankings without analysis;
- scraped stats without source context;
- AI-generated narration with no editorial point of view.

## Generic-template warning signs

Warning signs that originality is weak:

- the same sentence structure repeats for every player;
- the same visual pattern repeats without a reset;
- the narration could apply to any footballer;
- no claim has a source reference;
- no comparison explains why the topic matters;
- no counterpoint or nuance is included;
- no custom visual or stat card is present;
- the CTA is only “what do you think”; 
- title, first frame, and script do not share a specific angle;
- the package depends mainly on broadcast footage or web images.

## Weak versus stronger football framing

| Weak/generic framing | Stronger/original framing | Why stronger |
| --- | --- | --- |
| “Neymar is a great player.” | “Neymar’s legacy is judged through one injury, one expectation, and one unfinished World Cup question.” | Adds angle, stakes, and specificity. |
| “Messi is old now.” | “Messi’s 2026 question is not age alone; it is whether Argentina still needs him as a creator or symbol.” | Adds nuance and avoids generic age framing. |
| “Mbappe is fast.” | “Mbappe’s pressure is different because he is chasing history while already being treated like the standard.” | Adds pressure and record context. |
| “Yamal is young.” | “Yamal’s story is not just age; it is how quickly expectation turns into pressure.” | Adds emotional interpretation. |
| “Brazil lost badly.” | “Brazil’s collapse matters because one sequence changed the emotional direction of the tournament story.” | Adds event-based narrative. |

## Originality score bands

Use these bands for review:

| Band | Meaning |
| --- | --- |
| `0-2` | Very generic, likely low-effort or reused-content risk. |
| `3-4` | Some framing exists, but still template-heavy. |
| `5-6` | Usable for internal review, but originality improvements are needed. |
| `7-8` | Strong enough for editorial review if rights/facts are also clear. |
| `9-10` | Distinct point of view, strong evidence, strong visuals, and strong audience debate. |

## Required originality report fields

Future originality reports should include:

- `schema_version`;
- `package_id`;
- `content_type`;
- `originality_score`;
- `originality_status`;
- `signals_present`;
- `signals_missing`;
- `generic_template_warnings`;
- `required_actions`;
- `review_required`;
- `approval_state`;
- `notes`.

## monetization_risk_report.json linkage

The `monetization_risk_report.json` should use originality review to populate:

- `risk_categories.originality_risk.risk_level`;
- `risk_categories.originality_risk.review_required`;
- `risk_categories.originality_risk.publish_blocking`;
- `risk_categories.originality_risk.reason`;
- `risk_categories.originality_risk.required_actions`;
- `content_package_updates.originality_status`;
- `blocking_reasons`;
- `required_actions`.

If originality is missing, `publish_allowed` must remain `false`.

## content_package.json linkage

Originality requirements should link to P24/P25 fields:

- `packaging.title_options`;
- `packaging.first_frame_options`;
- `packaging.thumbnail_concepts`;
- `packaging.cta_comment_trigger_options`;
- `retention.genericness_risk`;
- `rights_and_monetization.originality_status`;
- `rights_and_monetization.blocking_reasons`;
- `rights_and_monetization.required_actions`.

Originality tracking can update package status to `originality_review_required` or `originality_blocked`, but it must not set `publish_allowed` to `true`.

## Example originality record

Example originality records are stored at:

```text
docs/operations/p26-originality-layer-example.json
```

The example includes:

- weak Short originality;
- stronger Short originality;
- stronger explainer originality;
- generic-template warnings;
- risk-report linkage fields.

## Stop conditions

Stop originality work if:

- a raw clip is treated as original by default;
- generic AI narration is treated as original by default;
- a slideshow of web images is treated as original by default;
- swapped player-name templates are treated as original by default;
- originality score is treated as rights clearance;
- originality score is treated as monetization approval;
- originality score is treated as publish approval;
- `publish_allowed` is changed to `true`;
- upload or publishing is introduced;
- workflow gate bypass is requested.

## Guardrails

- No automatic creative rewrite engine.
- No automatic host/avatar production.
- No automatic originality approval.
- No automatic reused-content clearance.
- No automatic monetization approval.
- No automatic rights clearance.
- No automatic publishing approval.
- No automatic upload.
- No automatic publishing.
- No unsupported claims.
- No misleading clickbait.
- No workflow gate bypass.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.

## Validation

Covered by:

```text
tests/integration/test_p26_step_04.py
```

The validation checks required originality signals, signal schema, Shorts and explainer minimum requirements, generic-template warning signs, weak versus stronger examples, score bands, future originality report fields, risk-report linkage, package linkage, stop conditions, guardrails, and P26 CI wildcard coverage.
