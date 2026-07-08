# P23 Step 02

This step documents the branch protection and required-check review boundary for production repository hardening.

Part of #313. Closes #315 after the PR merges.

## Goal

Define the required branch protection review points for the `test` branch, confirm the required implementation PR checks, and preserve the rule that no PR may be merged without exact-head CI on the current PR head SHA.

## Source references

This review builds on:

```text
docs/operations/p23-step-01.md
docs/operations/p22-readiness-report.md
docs/operations/p22-closeout-checklist.md
.github/workflows/p1-acceptance-harness.yml
```

## Review status

This branch protection and required-check review is documentation-only.

It does not:

- change branch protection settings;
- add required checks;
- remove required checks;
- enable auto-merge;
- disable auto-merge;
- merge a pull request;
- approve a pull request;
- bypass workflow gates;
- expose secret values;
- expose private runtime values;
- approve production launch;
- schedule production launch.

## Required implementation PR checks

Every implementation PR in this repository must preserve these required checks before merge:

```text
P1 Acceptance Harness
P1 Foundation Closeout
P1 Ops Storage
```

A PR is not merge-ready until all three checks complete successfully on the exact current PR head SHA.

## Exact-head CI rule

The exact-head CI rule means:

- identify the current PR head SHA immediately before evaluating CI;
- fetch workflow runs for that same SHA;
- confirm each required workflow run is completed;
- confirm each required workflow run conclusion is success;
- do not reuse CI evidence from an older commit;
- do not merge after a new commit is pushed until fresh CI passes on the new head;
- use an expected head SHA gate when merging.

## Branch protection review points

The manual branch protection review for `test` must cover:

- required status checks are enabled;
- required check names match the implementation workflow gate names;
- stale approvals are not relied on after new commits;
- direct pushes to protected branches are restricted where appropriate;
- force pushes are restricted where appropriate;
- deletions are restricted where appropriate;
- administrators understand whether protections apply to them;
- auto-merge remains disabled unless explicitly approved;
- branch rules are reviewed before production release;
- exceptions require a named owner, reason, expiry, and follow-up date.

## Required branch protection evidence

Evidence may record:

- issue or PR reference;
- merge commit reference;
- CI run identifier;
- branch name;
- required check name;
- required check result summary;
- exact head SHA;
- branch rule summary;
- exception summary;
- owner role;
- reviewer role;
- decision status;
- follow-up action.

Evidence must not include:

- private collaborator list;
- private team membership list;
- private email address list;
- private audit log export;
- secret value;
- token value;
- deploy key value;
- private runtime value;
- customer data;
- screenshot containing restricted data.

## Required review fields

A branch protection review note must record:

- review date;
- branch reviewed;
- required checks reviewed;
- exact-head CI rule reviewed;
- direct push restriction status;
- force push restriction status;
- deletion restriction status;
- auto-merge status;
- owner role;
- reviewer role;
- decision status;
- exception status;
- follow-up owner role;
- target review date;
- closure criterion.

## Stop conditions

Stop branch protection closeout if:

- required check names are missing;
- exact-head CI rule is missing;
- branch reviewed is missing;
- owner role is missing;
- reviewer role is missing;
- decision status is missing;
- exception has no named owner;
- exception has no expiry;
- exception has no follow-up date;
- CI evidence belongs to an older head SHA;
- one required check is missing;
- one required check is not successful;
- auto-merge is used without explicit approval;
- direct push bypass is requested;
- workflow gate bypass is requested;
- secret value is present;
- private runtime value is present;
- production launch is implied without explicit decision.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic branch protection changes.
- No automatic required-check changes.
- No automatic direct-push exception.
- No automatic force-push exception.
- No auto-merge.
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
tests/integration/test_p23_step_02.py
```

The validation checks source references, documentation-only status, required implementation checks, exact-head CI rule, branch protection review points, evidence boundaries, required review fields, stop conditions, and guardrails.