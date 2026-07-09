# P29 Step 01

This step defines the editorial status lifecycle and approval gates for generated content from draft through publish-export-ready output.

Part of #331. Closes #362 after the PR merges.

## Goal

Create a deterministic governance model that explains when generated content can move through editorial review, rights review, revisions, approval, publish-export readiness, external publish recording, and archival.

## Contract status

This step adds status documentation, a machine-readable example, and validation coverage only.

It does not:

- build a review UI;
- upload content to platforms;
- publish content;
- store platform credentials;
- clear rights automatically;
- approve editorial status automatically;
- bypass P26 publish-block rules;
- bypass workflow gates.

## Required statuses

The required status lifecycle is:

1. `draft`
2. `package_generated`
3. `editorial_review`
4. `rights_review`
5. `revisions_required`
6. `approved`
7. `publish_export_ready`
8. `published_external`
9. `archived`

## Status meanings

| Status | Meaning |
| --- | --- |
| `draft` | Content is being drafted and has no package or approval status. |
| `package_generated` | A content package exists, but human editorial review has not passed. |
| `editorial_review` | Human review is checking script, claims, structure, safety, and editorial quality. |
| `rights_review` | Human review is checking source attribution, footage, music, visual asset, and usage rights. |
| `revisions_required` | The package is blocked until requested edits are completed and resubmitted. |
| `approved` | Editorial and rights gates are passed, but publish export still needs final readiness checks. |
| `publish_export_ready` | All required gates are passed and the package may move to manual export/publish operations. |
| `published_external` | A human has published externally and recorded the external status; no API upload is implied. |
| `archived` | The package is no longer active for production or publishing. |

## Allowed transitions

| Current status | Allowed next statuses |
| --- | --- |
| `draft` | `package_generated`, `archived` |
| `package_generated` | `editorial_review`, `rights_review`, `revisions_required`, `archived` |
| `editorial_review` | `rights_review`, `revisions_required`, `approved`, `archived` |
| `rights_review` | `editorial_review`, `revisions_required`, `approved`, `archived` |
| `revisions_required` | `draft`, `package_generated`, `editorial_review`, `archived` |
| `approved` | `publish_export_ready`, `revisions_required`, `archived` |
| `publish_export_ready` | `published_external`, `revisions_required`, `archived` |
| `published_external` | `archived` |
| `archived` | none |

## Approval gates

To reach `approved`, the content must have:

- `editorial_gate_passed: true`;
- `rights_gate_passed: true`;
- `p26_publish_block_clear: true`;
- `source_attribution_complete: true`.

To reach `publish_export_ready`, the content must also have:

- `monetization_review_passed: true`.

No status implies publish-export readiness unless editorial, rights, source attribution, monetization, and P26 publish-block gates are clear.

## Blocked and revision-required states

`revisions_required` means a human reviewer has blocked progress until changes are completed.

Allowed blocker types are:

- `editorial_changes_required`;
- `rights_review_required`;
- `p26_publish_block`;
- `missing_source_attribution`;
- `monetization_review_required`;
- `platform_export_not_ready`.

Blocked content cannot move to:

- `approved`;
- `publish_export_ready`;
- `published_external`.

## P26 alignment

The model preserves P26 rules:

- P26 publish-block clearance is required;
- blocked content cannot be approved;
- blocked content cannot be publish-export-ready;
- risk review must remain visible in review records.

## Review record fields

A review record should include:

- `content_id`;
- `current_status`;
- `requested_status`;
- `reviewer_id`;
- `review_timestamp`;
- `gate_results`;
- `blockers`;
- `transition_allowed`.

## Example output

Example editorial status output is stored at:

```text
docs/operations/p29-editorial-status-example.json
```

## Validation

Validation is implemented in:

```text
src/editorial_status.py
tests/integration/test_p29_step_01.py
```

The validator checks:

- required statuses;
- allowed transitions;
- blocked/revision-required states;
- required approval gate fields;
- P26 publish-block alignment;
- no direct platform upload;
- no UI or upload scope;
- `publish_allowed: false`;
- `review_required: true`.

## Stop conditions

Stop work if a future change attempts to:

- build a review UI in P29-01;
- upload content to platforms;
- publish content automatically;
- store platform credentials or secrets;
- treat `approved` as direct publish permission;
- treat `publish_export_ready` as automatic upload permission;
- approve content while P26 publish blocks are active;
- skip rights review;
- skip source attribution review;
- skip monetization review;
- bypass workflow gates.

## Next step

After this PR merges, #363 can create the human review checklist for script, assets, and package review.
