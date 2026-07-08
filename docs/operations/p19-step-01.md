# P19 Step 01

This step documents secrets and configuration hardening controls for production security readiness.

Part of #261. Closes #262 after the PR merges.

## Goal

Define how secrets, configuration values, environment variables, redaction, evidence, and stop conditions must be handled before the system is considered security-hardened for production operation.

## Source references

This hardening guide builds on:

```text
docs/operations/p18-readiness-report.md
docs/operations/p18-step-01.md
docs/operations/p18-step-02.md
docs/operations/p18-step-04.md
docs/operations/p18-step-05.md
docs/operations/p17-readiness-report.md
docs/operations/p16-step-05.md
docs/operations/p14-step-06.md
```

## Hardening status

This guide is documentation-only.

It does not:

- create or rotate secrets;
- expose secret values;
- grant production access;
- change production configuration;
- approve production launch;
- schedule production launch;
- execute release activities;
- bypass workflow gates;
- publish configuration material;
- export configuration evidence.

## Secret handling rules

Secret handling must follow these rules:

- never commit secret values;
- never store production tokens in docs;
- never paste private runtime values into issues;
- never include raw credentials in CI evidence;
- never include private environment dumps in artifacts;
- use named placeholders for configuration references;
- store only summarized review notes;
- redact restricted values before evidence retention;
- route suspected exposure to security incident handling;
- require owner review before closing exposure findings.

## Configuration boundaries

Configuration review must distinguish:

- public configuration names;
- non-secret environment variable names;
- secret environment variable names;
- production-only values;
- development-only values;
- CI-only values;
- operator-facing configuration notes;
- restricted runtime values;
- configuration evidence summaries.

Do not record live production values.

## Environment variable expectations

Environment variable documentation may include:

- variable name placeholder;
- purpose summary;
- owner role;
- required or optional status;
- rotation expectation;
- environment scope;
- evidence sensitivity;
- validation route;
- escalation route.

Environment variable documentation must not include actual secret values.

## Forbidden evidence values

Forbidden evidence values include:

- passwords;
- API keys;
- OAuth tokens;
- session tokens;
- private signing keys;
- database credentials;
- production connection strings;
- cloud provider credentials;
- webhook secrets;
- private runtime values;
- raw environment dumps;
- customer data exports;
- external package exports.

## Redaction rules

Redaction must:

- remove exact restricted values;
- replace values with named placeholders;
- preserve enough context for review;
- record redaction owner;
- record redaction reason;
- record evidence sensitivity after redaction;
- route suspected exposure to security incident response;
- block closeout if redaction cannot be confirmed.

## Required hardening fields

Each hardening item must record:

- hardening item identifier;
- configuration area;
- owner;
- reviewer;
- evidence source;
- evidence sensitivity;
- secret exposure status;
- configuration review status;
- redaction status;
- action route;
- action owner;
- validation requirement;
- closure criteria.

## Hardening statuses

Allowed statuses:

- not started;
- ready for review;
- reviewed;
- reviewed with notes;
- exposure suspected;
- exposure confirmed;
- blocked;
- needs owner;
- needs evidence;
- rejected with reason;
- blocked by guardrail.

## Validation expectations

Validation must confirm:

- no docs require live secret values;
- no tests require live secret values;
- P19 integration tests are included in CI;
- forbidden value classes are documented;
- evidence exclusions are documented;
- redaction rules are documented;
- stop conditions are documented;
- guardrails are preserved.

## Evidence rules

Allowed evidence:

- issue or PR references;
- CI run identifiers;
- merge commit references;
- summarized configuration notes;
- summarized redaction notes;
- summarized hardening notes;
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
- raw logs with restricted values;
- rendered configuration materials;
- scheduled configuration outputs.

## Stop conditions

Stop hardening closure if:

- owner is missing;
- reviewer is missing;
- evidence source is missing;
- evidence sensitivity is missing;
- configuration review status is missing;
- redaction status is missing;
- suspected exposure has no action owner;
- confirmed exposure has no security incident route;
- actual secret value is present;
- private runtime value is present;
- raw credential is present;
- production token is present;
- customer data export is requested;
- external package export is requested;
- production configuration change is implied;
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
tests/integration/test_p19_step_01.py
```

The validation checks source references, documentation-only status, secret handling, configuration boundaries, environment variable expectations, forbidden evidence values, redaction rules, hardening fields, statuses, validation expectations, evidence rules, stop conditions, guardrails, and P19 CI wildcard coverage.
