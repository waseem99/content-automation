# P23 Step 05

This step documents the public/private evidence boundary review for production repository hardening.

Part of #313. Closes #318 after the PR merges.

## Goal

Define which production hardening evidence may be safely committed to the repository, which evidence must remain private or off-repository, and how redaction and minimization must be applied to CI, access, privacy, dependency, secrets, and operational evidence before production release.

## Source references

This review builds on:

```text
docs/operations/p23-step-01.md
docs/operations/p23-step-02.md
docs/operations/p23-step-03.md
docs/operations/p23-step-04.md
docs/operations/p22-step-01.md
docs/operations/p22-step-03.md
docs/operations/p22-step-05.md
docs/operations/p22-readiness-report.md
```

## Review status

This public/private evidence boundary review is documentation-only.

It does not:

- collect production evidence;
- export production evidence;
- publish evidence externally;
- commit private access lists;
- commit customer data;
- commit secret values;
- commit private runtime values;
- commit private package artifacts;
- change repository visibility;
- change collaborator access;
- approve production launch;
- schedule production launch;
- bypass workflow gates.

## Public repository evidence boundary

Evidence that may be committed to this repository must be limited to non-sensitive summaries and public operational references.

Allowed public repository evidence includes:

- issue reference;
- PR reference;
- merge commit reference;
- CI run identifier;
- workflow name;
- branch name;
- current head SHA;
- documentation path;
- test path;
- public configuration file name;
- non-sensitive decision status;
- role-level owner summary;
- role-level reviewer summary;
- redacted risk summary;
- follow-up action summary;
- closeout checklist status.

## Private or off-repository evidence boundary

Evidence that must remain private or off-repository includes:

- customer data;
- secret value;
- partial secret value;
- token value;
- token fragment;
- service account key;
- deploy key value;
- webhook signing secret;
- private runtime value;
- private environment dump;
- raw production log;
- raw deployment log;
- raw audit log export;
- private collaborator list;
- private team membership list;
- private account list;
- private email address list;
- private package artifact;
- private registry credential;
- screenshot containing restricted data;
- external package export.

## Redaction and minimization requirements

Before evidence is committed, the evidence owner must confirm:

- raw evidence is not required when a summary is enough;
- values are replaced with role-level or status-level summaries;
- private user names are omitted unless already public and necessary;
- private email addresses are omitted;
- secret names are included only when safe and necessary;
- secret values and fragments are removed;
- customer identifiers are removed;
- screenshots are avoided when text summaries are enough;
- any screenshot is reviewed for restricted values before use;
- logs are summarized instead of copied;
- package artifacts are not committed;
- external exports are not attached.

## Evidence handling categories

Each evidence item must be classified into one category:

- safe to commit as-is;
- safe to commit after redaction;
- safe to summarize only;
- private off-repository evidence;
- blocked by restricted data;
- blocked by missing owner review;
- blocked by workflow gate.

## Required evidence review fields

A public/private evidence boundary review note must record:

- review date;
- evidence item identifier;
- evidence category;
- source location;
- proposed repository location;
- sensitivity level;
- redaction status;
- minimization status;
- owner role;
- reviewer role;
- decision status;
- follow-up action;
- follow-up owner role;
- target review date;
- closure criterion.

## Stop conditions

Stop evidence boundary closeout if:

- evidence item identifier is missing;
- evidence category is missing;
- sensitivity level is missing;
- redaction status is missing;
- minimization status is missing;
- owner role is missing;
- reviewer role is missing;
- decision status is missing;
- follow-up owner role is missing for deferred actions;
- customer data is present;
- secret value is present;
- partial secret value is present;
- token value is present;
- token fragment is present;
- private runtime value is present;
- private environment dump is present;
- private access list is present;
- private package artifact is present;
- private registry credential is present;
- screenshot containing restricted data is present;
- external package export is requested;
- production evidence export is requested without explicit approval;
- production launch is implied without explicit decision;
- workflow gate bypass is requested.

## Manual review checklist

Before production release, confirm:

- committed evidence uses public operational references where possible;
- private evidence remains off-repository;
- customer data is not committed;
- secret values and fragments are not committed;
- private runtime values are not committed;
- private access lists are not committed;
- package registry credentials are not committed;
- private package artifacts are not committed;
- screenshots are avoided or reviewed before use;
- CI evidence references exact-head run identifiers only;
- follow-up actions have owner roles and target review dates;
- no evidence export was performed by this step.

## Guardrails

- No automatic approval.
- No automatic release.
- No automatic evidence collection.
- No automatic evidence export.
- No automatic repository visibility changes.
- No automatic access changes.
- No automatic secret reading.
- No automatic package publishing.
- No automatic package export.
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
tests/integration/test_p23_step_05.py
```

The validation checks source references, documentation-only status, public repository evidence boundaries, private or off-repository evidence boundaries, redaction and minimization requirements, evidence handling categories, required review fields, stop conditions, manual review checklist, and guardrails.