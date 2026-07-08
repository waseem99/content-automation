# P11 Step 04

This step documents production evidence archive maintenance for production operations stabilization.

Part of #157. Closes #161 after the PR merges.

## Goal

Maintain a clean production evidence archive that supports rollout review, alert tuning, incident review, and closeout without exposing private runtime values.

## Source references

This runbook builds on:

```text
docs/operations/p11-step-01.md
docs/operations/p11-step-03.md
docs/operations/p10-readiness-report.md
docs/operations/p10-closeout-checklist.md
```

## Archive structure

Recommended archive sections:

- rollout reviews;
- alert tuning reviews;
- incident reviews;
- deployment decisions;
- smoke test evidence;
- monitoring reviews;
- incident drill notes;
- owner handoff notes;
- closeout evidence.

## Evidence index

Each evidence entry must include:

- entry ID;
- date;
- source document;
- related issue or PR;
- owner;
- evidence type;
- redaction status;
- retention class;
- review date;
- disposal date if applicable.

## Retention classes

Use these retention classes:

- stabilization record;
- incident record;
- deployment decision record;
- monitoring review record;
- temporary working note.

Temporary working notes must either be promoted to a record or disposed after review.

## Access rules

Access rules:

- evidence archive owner manages structure;
- decision owner approves access changes;
- incident evidence is limited to operators who need it;
- public sharing is not allowed;
- raw secret values are not allowed;
- private runtime values are not allowed.

## Redaction rules

Before entry is accepted:

- remove tokens;
- remove connection strings;
- remove raw operator keys;
- remove private runtime values;
- remove unrelated personal information;
- preserve enough context for audit review.

## Review cadence

Review archive status:

- weekly during stabilization;
- after each incident review;
- after each alert tuning review;
- before P11 closeout;
- before any evidence disposal.

## Stop conditions

Stop archive update and escalate if:

- evidence includes secret values;
- owner is unknown;
- retention class is missing;
- entry lacks related issue or PR;
- access change lacks decision owner approval;
- disposal would remove active incident evidence;
- workflow gate bypass is requested.

## Guardrails

- No secret values in evidence.
- No private runtime values in notes.
- No public sharing of production evidence.
- No evidence disposal without review.
- No automatic approval.
- No workflow gate bypass.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p11_step_04.py
```

The validation checks source references, archive structure, evidence index, retention, access, redaction, review cadence, stop conditions, and guardrails.
