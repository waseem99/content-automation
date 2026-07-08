# P14 Step 05

This step documents audit package preparation for production compliance and audit readiness.

Part of #196. Closes #201 after the PR merges.

## Goal

Create an audit package structure that links production compliance evidence, review records, access certification, control testing, readiness checks, and evidence exclusions without exporting secret or private runtime material.

## Source references

This runbook builds on:

```text
docs/operations/p14-step-01.md
docs/operations/p14-step-02.md
docs/operations/p14-step-03.md
docs/operations/p14-step-04.md
docs/operations/p13-readiness-report.md
```

## Audit package contents

The audit package must include:

- package summary;
- production governance evidence index;
- compliance evidence map reference;
- security review cadence reference;
- access certification reference;
- control testing reference;
- operational runbook reference;
- incident and action tracking reference;
- resilience evidence reference;
- CI validation evidence reference;
- exception register reference;
- closeout readiness checklist.

## Package section mapping

Map package sections to evidence sources:

- governance section to release and lifecycle governance evidence;
- security section to security review records;
- access section to access certification records;
- controls section to control testing records;
- operations section to operator runbooks and action trackers;
- resilience section to backup, restore, failover, capacity, and drill records;
- validation section to PR references and CI run identifiers;
- exceptions section to accepted exceptions with owner and expiry date.

## Required package fields

Each package entry must record:

- package section;
- evidence source;
- evidence owner;
- package owner;
- reviewer;
- evidence status;
- latest review date;
- linked PR or issue reference;
- linked CI run identifier when applicable;
- exception owner when applicable;
- expiry date when applicable;
- package readiness status.

## Review flow

Audit package preparation follows this flow:

1. confirm package scope;
2. confirm evidence map is current;
3. confirm access certification evidence is complete;
4. confirm security review evidence is current;
5. confirm control testing evidence is complete;
6. confirm open actions have owners;
7. confirm accepted exceptions have expiry dates;
8. confirm excluded evidence is documented;
9. confirm readiness checklist is complete;
10. record final reviewer decision.

## Evidence exclusions

The package must exclude:

- secret values;
- private runtime values;
- raw credentials;
- production tokens;
- customer data exports;
- private environment dumps;
- external package exports;
- screenshots that reveal restricted runtime values.

Use references, identifiers, and archive entry names instead of sensitive evidence content.

## Readiness checks

The audit package is ready only when:

- every package section has an evidence source;
- every evidence source has an owner;
- every package section has a reviewer;
- evidence status is current;
- open actions have action owners;
- accepted exceptions have owners and expiry dates;
- excluded evidence is listed;
- final reviewer decision is recorded;
- no workflow gate bypass is requested.

## Stop conditions

Stop package readiness if:

- package scope is missing;
- evidence map is not current;
- access certification evidence is incomplete;
- security review evidence is missing;
- control testing evidence is incomplete;
- open action lacks owner;
- accepted exception lacks expiry date;
- evidence exclusion is not documented;
- package contains secret values;
- package contains private runtime values;
- external export is requested;
- workflow gate bypass is requested.

## Guardrails

- No audit package readiness without complete evidence references.
- No package section without owner and reviewer.
- No accepted exception without owner and expiry date.
- No secret values in evidence.
- No private runtime values in notes.
- No external export.
- No automatic approval.
- No workflow gate bypass.
- No publishing.
- No scheduling.
- No rendering.

## Validation

Covered by:

```text
tests/integration/test_p14_step_05.py
```

The validation checks source references, package contents, section mapping, required fields, review flow, evidence exclusions, readiness checks, stop conditions, and guardrails.
