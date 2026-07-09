# P28 Step 02

This step designs the `produce-longform` command and output contract for future 16:9 YouTube long-form video generation.

Part of #330. Closes #357 after the PR merges.

## Goal

Define the command interface, expected inputs, output folder structure, output file names, metadata bridge, source bridge, risk fields, and platform export connections for future long-form assembly work.

## Contract status

This is a design/specification step only.

It does not:

- implement full long-form assembly;
- render 16:9 video;
- upload to YouTube;
- connect YouTube Studio;
- ingest analytics;
- clear rights;
- approve monetization;
- approve editorial status;
- bypass P26 or P29 gates.

## Command

```bash
produce-longform \
  --concept docs/operations/p28-long-form-concept-example.json \
  --topic "Neymar 2014 World Cup injury and comeback pressure" \
  --subject "Neymar" \
  --output-dir outputs/longform/pkg-p28-longform-neymar-2014/ \
  --content-package content_package.json \
  --risk-report monetization_risk_report.json \
  --source-attribution source_attribution.json \
  --duration-minutes 7 \
  --review-only true \
  --dry-run true
```

## CLI arguments

| Argument | Required | Purpose |
| --- | --- | --- |
| `--concept` | Yes | Path to validated P28 long-form concept JSON/YAML input. |
| `--topic` | Yes | Football story/topic for the long-form plan. |
| `--subject` | Optional | Main player, club, match, tournament, or story subject. |
| `--output-dir` | Yes | Target folder for planned long-form outputs. |
| `--content-package` | Yes | Existing `content_package.json` or future generated package bridge. |
| `--risk-report` | Yes | P26 risk report input that must remain visible in outputs. |
| `--source-attribution` | Yes | Source attribution input used to create `source_list.json`. |
| `--duration-minutes` | Optional | Target duration constrained by the P28 long-form concept model. |
| `--review-only` | Yes | Forces review-only output and `publish_allowed: false`. |
| `--dry-run` | Optional | Validates inputs and output plan without producing media assets. |

## Expected inputs

The command design expects:

- validated P28 long-form concept file;
- `content_package.json` bridge input;
- `monetization_risk_report.json` risk input;
- `source_attribution.json` source input;
- rights review state;
- editorial review state;
- review-only command mode.

## Output folder structure

The default output folder pattern is:

```text
outputs/longform/{package_id}/
```

Example:

```text
outputs/longform/pkg-p28-longform-neymar-2014/
```

## Planned outputs

The required output contract is:

| Output | Purpose |
| --- | --- |
| `longform_plan.json` | Full production plan with concept, chapter map, packaging bridge, and review state. |
| `chapter_script.md` | Draft long-form chapter script organized by section type. |
| `source_list.json` | Source list and attribution plan for facts, visuals, and recreated assets. |
| `thumbnail_concepts.json` | Thumbnail concepts for future human design review. |
| `chapter_timestamps.json` | Approximate chapter timestamps for YouTube description packaging. |
| `sponsor_slot_notes.md` | Placeholder-only sponsor slot notes from the long-form concept. |
| `final_video_placeholder.txt` | Target final video location/name placeholder; no rendered video is produced in P28-02. |
| `content_package_link.json` | Bridge from long-form plan back to `content_package.json`. |
| `platform_export_links.json` | Bridge from long-form sections to future P27/P28 platform export packs after review. |
| `risk_review.json` | Risk fields carried into the long-form output manifest. |
| `metadata.json` | Command metadata, schema, package id, output folder, and review-only flags. |

## Relationship to content_package.json

Long-form output must reference `content_package.json` instead of replacing it.

The bridge file `content_package_link.json` must include:

- `content_package_path`;
- `longform_plan_path`;
- `risk_report_path`;
- `source_attribution_path`;
- source package status.

## Relationship to platform export packs

Long-form outputs connect to platform export packs through `platform_export_links.json`.

This bridge records:

- future YouTube long-form packaging status;
- Shorts cutdown candidates;
- P27 export compatibility after review;
- direct upload out-of-scope status.

No platform upload or live preview is introduced by this step.

## Risk fields

The output contract must preserve:

- `rights_review_required: true`;
- `factual_review_required: true`;
- `monetization_review_required: true`;
- `source_attribution_required: true`;
- `editorial_review_required: true`;
- `publish_allowed: false`;
- `review_required: true`.

## Example output

Example output contract is stored at:

```text
docs/operations/p28-produce-longform-output-contract-example.json
```

## Validation

Validation is implemented in:

```text
src/long_form_command_contract.py
tests/integration/test_p28_step_02.py
```

The validation confirms the design includes:

- required CLI arguments;
- required output folder pattern;
- required output file names;
- script, chapters, metadata, sources, packaging, and risk fields;
- example command;
- `content_package.json` connection;
- P27 platform export pack connection;
- rendering/upload remains out of scope.

## Stop conditions

Stop work if a future change attempts to:

- render a 16:9 video in P28-02;
- implement full long-form assembly in P28-02;
- introduce YouTube upload APIs;
- connect YouTube Studio analytics;
- store platform credentials;
- store secrets;
- commit external video assets;
- set `publish_allowed` to `true`;
- skip rights, factual, monetization, source attribution, or editorial review;
- bypass P26 or P29 gates;
- bypass workflow gates.

## Next step

After this PR merges, #358 can add series and episode metadata contracts that can reference the `produce-longform` output model.
