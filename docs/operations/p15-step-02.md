# P15 Step 02

This step documents a safe automation opportunity review process for production continuous improvement and optimization.

Part of #209. Closes #211 after the PR merges.

## Goal

Identify automation candidates that can reduce manual production effort while keeping every opportunity recommendation-only until explicitly approved through the required governance path.

## Source references

This runbook builds on:

```text
docs/operations/p15-step-01.md
docs/operations/p14-readiness-report.md
docs/operations/p14-closeout-checklist.md
```

## Candidate categories

Review automation candidates in these categories:

- evidence collection assistance;
- runbook consistency checks;
- documentation freshness checks;
- alert triage assistance;
- operational checklist preparation;
- cost and performance signal aggregation;
- support trend grouping;
- incident action tracking reminders;
- validation evidence summarization;
- backlog hygiene checks.

## Required candidate fields

Each automation candidate must record:

- candidate identifier;
- candidate category;
- manual step being reduced;
- expected benefit;
- risk level;
- approval boundary;
- source evidence;
- candidate owner;
- reviewer;
- security reviewer when applicable;
- validation owner;
- recommended next action;
- decision status;
- stop condition review;
- linked issue or PR when applicable.

## Risk review

Risk review must check:

- whether the automation could approve work automatically;
- whether the automation could bypass workflow gates;
- whether the automation could publish, schedule, render, or externally export content;
- whether the automation could expose secret values;
- whether the automation could expose private runtime values;
- whether a human reviewer remains in the decision path;
- whether validation evidence is required before implementation.

## Candidate scoring

Score each candidate on:

- manual effort reduced;
- repeat frequency;
- operational risk;
- review complexity;
- validation complexity;
- evidence sensitivity;
- rollback simplicity;
- owner availability.

Allowed recommendations:

- recommend implementation issue;
- recommend manual process only;
- recommend more evidence;
- recommend blocked by guardrail;
- recommend reject with reason.

## Approval boundary

Automation review can only recommend next action. It cannot:

- approve the automation;
- merge implementation;
- bypass CI;
- bypass human review;
- bypass release calendar controls;
- create production launch approval;
- publish, schedule, render, or externally export content.

Any implementation still requires a scoped issue, branch, PR, exact-head CI, and merge approval under the existing workflow.

## Ownership expectations

Required ownership:

- candidate owner;
- reviewer;
- security reviewer when sensitive evidence is involved;
- validation owner when implementation is recommended;
- action owner when follow-up is required;
- exception owner when an exception is proposed.

Ownerless candidates cannot be recommended for implementation.

## Stop conditions

Stop automation recommendation if:

- candidate owner is missing;
- reviewer is missing;
- source evidence is missing;
- approval boundary is missing;
- risk level is missing;
- validation owner is missing for implementation recommendation;
- candidate could approve work automatically;
- candidate could bypass workflow gates;
- candidate could publish, schedule, render, or externally export content;
- candidate could expose secret values;
- candidate could expose private runtime values;
- exception has no owner or expiry date.

## Guardrails

- No automatic approval.
- No workflow gate bypass.
- No public production launch without explicit decision.
- No release without calendar entry.
- No release during blackout window.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No secret values in evidence.
- No private runtime values in notes.
- No permanent exceptions.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p15_step_02.py
```

The validation checks source references, candidate categories, required fields, risk review, scoring, approval boundary, ownership expectations, stop conditions, and guardrails.
