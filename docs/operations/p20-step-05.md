# P20 Step 05

This step documents the third-party dependency compliance evidence pack for production compliance readiness.

Part of #274. Closes #279 after the PR merges.

## Goal

Define audit-ready evidence for dependency review, package source, vulnerability routing, lockfile and manifest handling, license or usage notes, and external package export restrictions.

## Source references

This evidence pack builds on:

```text
docs/operations/p20-step-02.md
docs/operations/p20-step-03.md
docs/operations/p19-step-04.md
docs/operations/p19-step-01.md
docs/operations/p19-readiness-report.md
docs/operations/p15-readiness-report.md
docs/operations/p14-step-06.md
```

## Pack status

This dependency compliance evidence pack is documentation-only.

It does not:

- update dependencies;
- install packages;
- modify lockfiles;
- publish package artifacts;
- export package bundles;
- approve production launch;
- schedule production launch;
- bypass workflow gates;
- replace scoped implementation issues;
- replace exact-head CI.

## Evidence categories

The pack must cover evidence for:

- dependency inventory review;
- package source review;
- direct dependency classification;
- transitive dependency awareness;
- runtime dependency classification;
- development dependency classification;
- vulnerability routing;
- lockfile and manifest handling;
- license or usage note review;
- dependency change audit trail;
- external package export restrictions.

## Required evidence fields

Each dependency compliance evidence item must record:

- evidence item identifier;
- dependency name placeholder;
- dependency type;
- package source;
- manifest path;
- lockfile path when present;
- current version placeholder;
- requested version placeholder;
- vulnerability status;
- license or usage note status;
- owner;
- reviewer;
- source issue or PR;
- final head SHA when changed;
- CI run identifiers when changed;
- merge commit when changed;
- evidence sensitivity;
- action route;
- closure criteria.

## Package source review

Package source review must confirm:

- package source is recorded;
- dependency type is recorded;
- package purpose is summarized;
- owner is recorded;
- reviewer is recorded;
- source evidence is summary-only;
- no package bundle is exported;
- no raw dependency archive is attached;
- no external package export is requested.

## Vulnerability routing

Vulnerability routing statuses:

- no known issue recorded;
- informational;
- low;
- medium;
- high;
- critical;
- owner review required;
- security incident escalation required;
- blocked by guardrail.

High or critical findings require owner review and escalation before closeout.

## Lockfile and manifest handling

Lockfile and manifest evidence must record:

- manifest path;
- lockfile path when present;
- package change summary;
- transitive change summary;
- validation command summary;
- exact-head CI evidence;
- rollback route;
- closure criteria.

Lockfile or manifest changes require scoped issue, scoped PR, and exact-head CI.

## License or usage notes

License or usage notes must record:

- license or usage note status;
- reviewer;
- evidence source;
- action route;
- escalation route when unclear;
- closure criteria.

This pack does not provide legal advice or approve external redistribution.

## Allowed evidence

Allowed evidence:

- issue or PR reference;
- CI run identifier;
- merge commit reference;
- manifest path;
- lockfile path;
- summarized dependency note;
- summarized vulnerability note;
- summarized license or usage note;
- summarized reviewer note;
- evidence archive entry name.

## Forbidden evidence

Forbidden evidence:

- external package export;
- package bundle export;
- raw dependency archive;
- private package artifact;
- secret value;
- private runtime value;
- raw credential;
- production token;
- customer data export;
- raw log with restricted value.

## Stop conditions

Stop dependency compliance closure if:

- evidence item identifier is missing;
- dependency name placeholder is missing;
- dependency type is missing;
- package source is missing;
- owner is missing;
- reviewer is missing;
- source issue or PR is missing for a change;
- final head SHA is missing for a change;
- CI run identifier is missing for a change;
- merge commit is missing for a change;
- vulnerability status is missing;
- high or critical finding has no escalation route;
- lockfile status is missing when lockfile is present;
- license or usage note status is missing;
- external package export is requested;
- package bundle export is requested;
- customer data export is requested;
- secret value is present;
- private runtime value is present;
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
tests/integration/test_p20_step_05.py
```

The validation checks source references, documentation-only status, evidence categories, required fields, package source review, vulnerability routing, lockfile and manifest handling, license or usage notes, allowed evidence, forbidden evidence, stop conditions, and guardrails.
