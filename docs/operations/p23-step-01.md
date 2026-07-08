# P23 Step 01

This step documents the repository visibility and access review boundary for production repository hardening.

Part of #313. Closes #314 after the PR merges.

## Goal

Record the current repository visibility state, define the manual access review that must happen before production release, and preserve the guardrail that repository visibility and collaborator access are not changed automatically by documentation or CI work.

## Source references

This review builds on:

```text
docs/operations/p22-readiness-report.md
docs/operations/p22-closeout-checklist.md
docs/operations/p22-step-01.md
docs/operations/p22-step-03.md
docs/operations/p22-step-04.md
docs/operations/p22-step-05.md
```

## Review status

This repository visibility and access review is documentation-only.

It does not:

- change repository visibility;
- add repository collaborators;
- remove repository collaborators;
- modify repository roles;
- grant admin access;
- revoke admin access;
- expose private access lists;
- expose secret values;
- expose private runtime values;
- approve production launch;
- schedule production launch;
- bypass workflow gates.

## Current repository observation

GitHub repository metadata observed during P23 planning showed:

```text
repository: waseem99/content-automation
default branch: test
visibility: public
auto-merge: disabled
```

The public visibility state is treated as a production hardening risk boundary because repository contents, issue references, PR metadata, documentation, and evidence patterns may be externally visible while the repository remains public.

## Required manual visibility decision

Before production release, the repository owner must make and record one of these decisions:

- return the repository to private;
- keep the repository public with an explicit accepted-risk note;
- defer the visibility change with a named owner, reason, and target review date.

The default hardening recommendation is to return the repository to private when CI no longer requires public visibility.

## Access review scope

The access review must cover:

- repository owner;
- administrator users;
- maintain users;
- write users;
- triage users;
- read-only users;
- deploy key holders;
- automation identities;
- GitHub Actions permissions;
- external integrations with repository access.

Only role names and summarized counts may be included in repository evidence. Private user lists, email addresses, invitation links, deploy key material, and token material must not be committed.

## Evidence allowed in this repository

Allowed evidence for this step:

- issue or PR reference;
- merge commit reference;
- CI run identifier;
- current visibility summary;
- default branch name;
- auto-merge setting summary;
- access review owner role;
- manual decision status;
- non-sensitive risk summary;
- follow-up action owner role.

## Evidence prohibited in this repository

Do not commit:

- private collaborator list;
- private team membership list;
- private email address list;
- invitation URL;
- deploy key value;
- token value;
- secret value;
- private runtime value;
- customer data;
- raw audit log export;
- screenshot containing restricted data;
- external package export.

## Required access review fields

A production access review note must record:

- review date;
- repository reviewed;
- visibility state;
- default branch;
- owner role;
- reviewer role;
- access category reviewed;
- evidence location;
- decision status;
- follow-up action;
- follow-up owner role;
- target review date;
- closure criterion.

## Stop conditions

Stop repository hardening closeout if:

- repository visibility is public and no manual decision is recorded;
- owner role is missing;
- reviewer role is missing;
- access category reviewed is missing;
- decision status is missing;
- follow-up owner role is missing for deferred actions;
- target review date is missing for deferred actions;
- private collaborator list is included in repository evidence;
- secret value is present;
- private runtime value is present;
- customer data is present;
- deploy key value is present;
- token value is present;
- raw audit log export is requested for commit;
- production launch is implied without explicit decision;
- workflow gate bypass is requested.

## Manual action checklist

Before production release, confirm:

- repository visibility decision is recorded;
- public/private evidence boundary is understood;
- owner/admin access review is completed or formally deferred;
- automation identities are reviewed without exposing values;
- GitHub Actions permissions are reviewed without exposing secrets;
- required CI checks remain enforced through PR workflow;
- no automatic access change was made by this step;
- no automatic visibility change was made by this step.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic visibility changes.
- No automatic access changes.
- No automatic collaborator changes.
- No automatic deploy key changes.
- No automatic secret rotation.
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
tests/integration/test_p23_step_01.py
```

The validation checks source references, documentation-only status, repository observation, manual visibility decision, access review scope, allowed and prohibited evidence, required access review fields, stop conditions, guardrails, and P23 CI wildcard coverage.