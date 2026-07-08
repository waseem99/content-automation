# P23 Step 04

This step documents dependency and package access review controls for production repository hardening.

Part of #313. Closes #317 after the PR merges.

## Goal

Define how dependency sources, package registry access, package publishing rights, and external distribution boundaries must be reviewed before production release without exposing credentials or enabling automatic package publication or export.

## Source references

This review builds on:

```text
docs/operations/p23-step-01.md
docs/operations/p23-step-02.md
docs/operations/p23-step-03.md
docs/operations/p22-step-05.md
docs/operations/p22-readiness-report.md
requirements.txt
```

## Review status

This dependency and package access review is documentation-only.

It does not:

- install new dependencies;
- upgrade dependencies;
- remove dependencies;
- publish packages;
- export private packages;
- create package registry credentials;
- rotate package registry credentials;
- expose package registry credentials;
- add package maintainers;
- remove package maintainers;
- approve production launch;
- schedule production launch;
- bypass workflow gates.

## Dependency review boundary

The dependency review must cover:

- dependency source file;
- runtime dependency category;
- development dependency category;
- package registry source;
- pinned or ranged version summary;
- license review status;
- security review status;
- owner role;
- reviewer role;
- follow-up action status.

The review may summarize dependency names and public package names, but it must not include private package credentials, package registry tokens, private index URLs with credentials, or private package artifacts.

## Package access review boundary

The package access review must cover:

- package registry name;
- package namespace or scope summary;
- package owner role;
- package maintainer role;
- publish permission summary;
- read permission summary;
- automation identity summary;
- token storage location summary;
- external distribution status;
- package export decision status.

Only role-level and status-level summaries may be committed. Private account lists, credential values, package tokens, service account keys, and private registry URLs with embedded credentials must not be committed.

## Publishing and distribution decision boundary

A package publishing or external distribution decision must be manual and must record one of these statuses:

- no package publishing approved;
- publishing blocked until explicit production decision;
- private package distribution approved outside repository evidence;
- external package export rejected;
- external package export deferred with owner, reason, and target review date;
- blocked because registry credential exposure is suspected and escalation is required.

This step does not approve, perform, or schedule package publishing or export.

## Evidence allowed in this repository

Allowed evidence for this step:

- issue or PR reference;
- merge commit reference;
- CI run identifier;
- dependency source file name;
- public dependency name;
- package registry name;
- package namespace summary;
- owner role;
- reviewer role;
- publish permission summary;
- package export decision status;
- security review status;
- license review status;
- non-sensitive risk summary;
- follow-up action status.

## Evidence prohibited in this repository

Do not commit:

- package registry credential;
- package registry token;
- private index URL with credential;
- private package artifact;
- private maintainer list;
- private account list;
- service account key;
- deploy key value;
- token value;
- secret value;
- private runtime value;
- customer data;
- external package export;
- raw registry audit export;
- screenshot containing restricted data.

## Required review fields

A dependency and package access review note must record:

- review date;
- dependency source reviewed;
- package registry reviewed;
- package namespace or scope summary;
- owner role;
- reviewer role;
- evidence location;
- license review status;
- security review status;
- publish permission summary;
- package export decision status;
- follow-up action;
- follow-up owner role;
- target review date;
- closure criterion.

## Stop conditions

Stop dependency and package access closeout if:

- dependency source reviewed is missing;
- package registry reviewed is missing;
- owner role is missing;
- reviewer role is missing;
- license review status is missing;
- security review status is missing;
- publish permission summary is missing;
- package export decision status is missing;
- follow-up owner role is missing for deferred actions;
- target review date is missing for deferred actions;
- package registry credential is present;
- package registry token is present;
- private index URL with credential is present;
- private package artifact is present;
- private maintainer list is present;
- service account key is present;
- token value is present;
- secret value is present;
- private runtime value is present;
- customer data is present;
- external package export is requested without explicit approval;
- registry credential exposure is suspected and no escalation route exists;
- production launch is implied without explicit decision;
- workflow gate bypass is requested.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic dependency install.
- No automatic dependency upgrade.
- No automatic dependency removal.
- No automatic package publishing.
- No automatic package export.
- No automatic registry credential changes.
- No automatic package maintainer changes.
- No workflow gate bypass.
- No public production launch without explicit decision.
- No implementation without scoped issue and PR.
- No merge without exact-head CI.
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
tests/integration/test_p23_step_04.py
```

The validation checks source references, documentation-only status, dependency review boundaries, package access review boundaries, publishing and distribution decision boundaries, evidence boundaries, required review fields, stop conditions, and guardrails.