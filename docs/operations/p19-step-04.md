# P19 Step 04

This step documents dependency and supply-chain review controls for production security readiness.

Part of #261. Closes #265 after the PR merges.

## Goal

Define dependency review, package update policy, lockfile expectations, vulnerable dependency routing, CI evidence, and stop conditions for safe supply-chain operation.

## Source references

This supply-chain review builds on:

```text
docs/operations/p19-step-01.md
docs/operations/p19-step-02.md
docs/operations/p19-step-03.md
docs/operations/p18-step-01.md
docs/operations/p18-step-05.md
docs/operations/p15-readiness-report.md
docs/operations/p14-step-06.md
```

## Review status

This supply-chain review is documentation-only.

It does not:

- update production dependencies;
- install new packages;
- modify lockfiles;
- publish package artifacts;
- export package bundles;
- approve production launch;
- schedule production launch;
- bypass workflow gates;
- replace scoped implementation issues;
- replace exact-head CI.

## Dependency review process

Dependency review must include:

- dependency inventory review;
- direct dependency identification;
- transitive dependency awareness;
- runtime dependency classification;
- development dependency classification;
- security-sensitive dependency classification;
- package source review;
- license or usage note review;
- vulnerability signal review;
- update route selection;
- exact-head CI confirmation;
- evidence-safe closeout.

## Package update policy

Package updates must:

- start from a scoped issue;
- use a scoped branch from `test`;
- describe the package and reason;
- document expected impact;
- preserve lockfile consistency;
- run exact-head CI;
- record CI run identifiers;
- avoid unrelated dependency updates;
- route vulnerability fixes through owner review;
- avoid automatic merge or automatic approval.

## Lockfile expectations

Lockfile handling must define:

- lockfile path when present;
- dependency manifest path;
- update owner;
- reviewer;
- package change summary;
- transitive change summary;
- validation command summary;
- exact-head CI evidence;
- rollback route;
- closure criteria.

Lockfile or manifest changes require scoped PR review.

## Vulnerability routing

Vulnerability review must record:

- vulnerability identifier placeholder;
- affected dependency;
- severity level;
- affected scope;
- owner;
- reviewer;
- evidence source;
- remediation route;
- temporary mitigation route;
- target follow-up route;
- closure criteria.

Severity levels:

- informational;
- low;
- medium;
- high;
- critical;
- blocked by guardrail.

High or critical findings require escalation to security incident response or a scoped implementation issue.

## External package export restrictions

External package export is prohibited unless represented only by:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- summarized package review note;
- evidence archive entry name.

Do not attach package bundles, private artifacts, raw dependency archives, or customer data exports to evidence.

## Required review fields

Each dependency review item must record:

- review item identifier;
- dependency name placeholder;
- dependency type;
- package source;
- current version placeholder;
- requested version placeholder;
- owner;
- reviewer;
- vulnerability status;
- lockfile status;
- CI evidence source;
- evidence sensitivity;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Action routes

Allowed action routes:

- no update required;
- update documentation only;
- create implementation issue;
- create security issue;
- update dependency with scoped PR;
- hold update with reason;
- reject with reason;
- escalate to security incident response;
- block by guardrail.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized dependency notes;
- summarized vulnerability notes;
- summarized lockfile notes;
- summarized reviewer notes;
- evidence archive entry names.

Do not store:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- private environment dumps;
- customer data exports;
- external package exports;
- package bundle exports;
- raw dependency archives;
- rendered package materials;
- scheduled package outputs.

## Stop conditions

Stop supply-chain review closure if:

- dependency name is missing;
- owner is missing;
- reviewer is missing;
- package source is missing;
- vulnerability status is missing;
- lockfile status is missing when lockfile is present;
- CI evidence source is missing for dependency change;
- high or critical finding has no escalation route;
- package update lacks scoped issue;
- dependency change bypasses exact-head CI;
- automatic approval is implied;
- external package export is requested;
- customer data export is requested;
- evidence contains secret values;
- evidence contains private runtime values;
- production launch is implied;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic dependency approval.
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
tests/integration/test_p19_step_04.py
```

The validation checks source references, documentation-only status, dependency review process, package update policy, lockfile expectations, vulnerability routing, external export restrictions, required fields, action routes, evidence rules, stop conditions, and guardrails.
