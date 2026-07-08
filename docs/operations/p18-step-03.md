# P18 Step 03

This step documents the training and onboarding checklist for production handover and operator enablement.

Part of #248. Closes #251 after the PR merges.

## Goal

Define the onboarding sequence, required reading, validation questions, manual sign-off, evidence handling checks, and escalation readiness needed before operators or support staff take ownership of production procedures.

## Source references

This checklist builds on:

```text
docs/operations/p18-step-01.md
docs/operations/p18-step-02.md
docs/operations/p17-readiness-report.md
docs/operations/p17-step-01.md
docs/operations/p17-step-02.md
docs/operations/p17-step-03.md
docs/operations/p17-step-04.md
docs/operations/p17-step-05.md
docs/operations/p16-readiness-report.md
docs/operations/p15-readiness-report.md
```

## Checklist status

This checklist is documentation-only.

It does not:

- grant production access;
- approve production launch;
- schedule production launch;
- execute release activities;
- replace role-based procedures;
- replace support escalation;
- publish onboarding material;
- render training material;
- export onboarding evidence;
- bypass workflow gates.

## Onboarding sequence

The onboarding sequence must include:

1. confirm assigned role;
2. review operator handover guide;
3. review role-based procedure;
4. review release readiness context;
5. review observability context;
6. review evidence handling rules;
7. complete validation questions;
8. complete escalation readiness check;
9. complete manual role sign-off;
10. record evidence-safe onboarding completion.

## Required reading

Operators and support staff must review:

- P18 operator handover guide;
- P18 role-based operating procedures;
- P17 release readiness report;
- P17 release decision pack;
- P17 production release checklist;
- P17 dry-run and rehearsal process;
- P17 Go / No-Go approval record;
- P17 post-release observation plan;
- P16 observability readiness report;
- P15 continuous improvement readiness report.

## Validation questions

Each onboarded person must answer validation questions covering:

- branch creation rules;
- PR title and body rules;
- exact-head CI requirement;
- required check names;
- same-branch patching;
- issue closure confirmation;
- manual approval requirement;
- release calendar requirement;
- blackout window requirement;
- evidence safety rules;
- support escalation route;
- incident escalation route;
- restricted evidence exclusions;
- stop conditions.

## Role sign-off

Manual role sign-off must record:

- trainee name or role placeholder;
- assigned role;
- role owner;
- reviewer;
- required reading completion;
- validation question completion;
- evidence handling acknowledgement;
- escalation readiness acknowledgement;
- stop condition acknowledgement;
- sign-off status;
- sign-off date placeholder;
- follow-up route.

Sign-off cannot be automatic.

## Evidence handling check

The onboarding evidence handling check must confirm:

- allowed evidence types are understood;
- restricted evidence types are understood;
- evidence sensitivity is recorded;
- evidence source is recorded;
- customer data export is blocked;
- external package export is blocked;
- raw credentials are blocked;
- production tokens are blocked;
- private runtime values are blocked;
- raw logs with restricted values are blocked.

## Escalation readiness check

Escalation readiness must confirm the trainee knows when to escalate:

- exact-head CI fails;
- workflow cannot start;
- issue scope is unclear;
- PR scope expands;
- owner is missing;
- reviewer is missing;
- release decision is requested;
- blackout conflict appears;
- support case has no owner;
- incident signal appears;
- restricted evidence appears;
- workflow gate bypass is requested.

## Required onboarding fields

Each onboarding record must include:

- onboarding item identifier;
- assigned role;
- trainee placeholder;
- role owner;
- reviewer;
- required reading status;
- validation question status;
- evidence handling status;
- escalation readiness status;
- manual sign-off status;
- evidence source;
- evidence sensitivity;
- action route;
- action owner;
- closure criteria.

## Onboarding statuses

Allowed statuses:

- not started;
- in progress;
- ready for review;
- signed off;
- signed off with notes;
- blocked;
- needs owner;
- needs reviewer;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized onboarding notes;
- summarized validation notes;
- summarized sign-off notes;
- summarized escalation readiness notes;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- raw logs with restricted values;
- rendered training materials;
- scheduled onboarding outputs.

## Stop conditions

Stop onboarding closure if:

- assigned role is missing;
- role owner is missing;
- reviewer is missing;
- required reading is incomplete;
- validation questions are incomplete;
- evidence handling check is incomplete;
- escalation readiness check is incomplete;
- manual sign-off is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- automatic sign-off is implied;
- production launch is implied;
- workflow gate bypass is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- customer data export is requested;
- external export is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic sign-off.
- No workflow gate bypass.
- No public production launch without explicit decision.
- No release without calendar entry.
- No release during blackout window.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
- No permanent exceptions.
- No secret values in evidence.
- No private runtime values in notes.
- No customer data exports.
- No external package exports.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p18_step_03.py
```

The validation checks source references, documentation-only status, onboarding sequence, required reading, validation questions, role sign-off, evidence handling, escalation readiness, onboarding fields, statuses, evidence rules, stop conditions, and guardrails.
