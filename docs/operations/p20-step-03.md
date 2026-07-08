# P20 Step 03

This step documents the audit trail and change evidence review for production compliance readiness.

Part of #274. Closes #277 after the PR merges.

## Goal

Define how issues, branches, pull requests, exact-head CI, merge commits, closeout reports, and parent epic evidence form a traceable audit trail.

## Source references

This review builds on:

```text
docs/operations/p20-step-01.md
docs/operations/p20-step-02.md
docs/operations/p19-readiness-report.md
docs/operations/p18-readiness-report.md
docs/operations/p17-readiness-report.md
docs/operations/p16-readiness-report.md
docs/operations/p15-readiness-report.md
```

## Review status

This audit trail review is documentation-only.

It does not:

- approve production launch;
- schedule production launch;
- merge changes;
- bypass workflow gates;
- alter branch protection;
- create audit exports;
- publish audit evidence;
- render audit evidence;
- replace exact-head CI;
- replace scoped issues and PRs.

## Audit trail components

Required audit trail components:

- parent epic;
- scoped child issue;
- branch created from `test`;
- PR with exact title and body format;
- changed files list;
- final PR head SHA;
- required exact-head CI run identifiers;
- merge commit reference;
- issue closure confirmation;
- parent epic closeout evidence;
- readiness report;
- closeout checklist;
- validation test.

## Change evidence fields

Each change evidence item must record:

- change evidence identifier;
- parent epic number;
- child issue number;
- branch name;
- PR number;
- PR title;
- PR body status;
- final head SHA;
- required CI run identifiers;
- CI conclusion;
- merge commit;
- issue closure status;
- evidence sensitivity;
- owner;
- reviewer;
- closure criteria.

## Traceability rules

Traceability must prove:

- every implementation has a scoped issue;
- every implementation branch starts from `test`;
- every PR closes the scoped issue;
- every PR uses the required title format;
- every PR uses the required body format;
- every final merge uses the final exact head;
- every required check is green on the final exact head;
- every issue closes after merge;
- every epic closes only after final closeout evidence.

## Required checks

Required checks for closeout evidence:

- P1 Acceptance Harness;
- P1 Foundation Closeout;
- P1 Ops Storage.

No merge or closeout may be treated as valid without exact-head CI evidence.

## Exception handling

Audit exceptions must record:

- exception identifier;
- affected issue or PR;
- exception owner;
- reviewer;
- business reason summary;
- expiry or review point;
- compensating control;
- evidence source;
- escalation route;
- closure criteria.

Exceptions cannot bypass required CI, scoped issue workflow, or restricted evidence guardrails.

## Allowed evidence

Allowed evidence:

- issue or PR reference;
- branch name;
- final head SHA;
- CI run identifier;
- merge commit reference;
- summarized review note;
- summarized closeout note;
- readiness report path;
- closeout checklist path;
- validation test path.

## Forbidden evidence

Forbidden evidence:

- secret value;
- private runtime value;
- raw credential;
- production token;
- customer data export;
- external package export;
- raw log with restricted value;
- rendered audit material;
- scheduled audit output.

## Stop conditions

Stop audit trail closure if:

- parent epic number is missing;
- child issue number is missing;
- branch name is missing;
- PR number is missing;
- final head SHA is missing;
- required CI run identifier is missing;
- CI conclusion is not success;
- merge commit is missing;
- issue closure status is missing;
- owner is missing;
- reviewer is missing;
- exact-head CI evidence is missing;
- scoped issue linkage is missing;
- exception attempts to bypass CI;
- secret value is present;
- private runtime value is present;
- customer data export is requested;
- external export is requested;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
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
tests/integration/test_p20_step_03.py
```

The validation checks source references, documentation-only status, audit trail components, change evidence fields, traceability rules, required checks, exception handling, allowed evidence, forbidden evidence, stop conditions, and guardrails.
