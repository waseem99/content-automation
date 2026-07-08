# P11 Step 02

This step documents alert tuning and threshold review for production operations stabilization.

Part of #157. Closes #159 after the PR merges.

## Goal

Create a repeatable review process for alert quality, thresholds, routing health, noisy signals, missed signals, and owner follow-up.

## Source references

This runbook builds on:

```text
docs/operations/p11-step-01.md
docs/operations/p10-step-04.md
docs/operations/p10-step-05.md
```

## Alert inventory

Maintain an inventory for:

- healthcheck failure;
- readiness failure;
- repeated 5xx responses;
- database connection failure;
- migration readiness failure;
- protected route access anomaly;
- queue growth;
- workflow failure spike;
- audit report request failure;
- missing observability signal.

## Threshold review

For each alert, record:

- current threshold;
- current route;
- primary owner;
- backup owner;
- expected action;
- recent trigger count;
- false positive count;
- missed signal count;
- proposed threshold change;
- final decision.

## Noisy signal review

A signal is noisy when it triggers without required action. Review:

- trigger pattern;
- affected route;
- owner feedback;
- proposed suppression rule;
- proposed threshold change;
- risk of suppression;
- review date.

## Missed signal review

A missed signal exists when expected alerting did not occur. Review:

- expected trigger;
- observed symptom;
- missing route or missing metric;
- owner assigned;
- corrective action;
- due date;
- validation method.

## Review outputs

Record:

- reviewed alerts;
- threshold changes;
- route changes;
- owner changes;
- noisy signals accepted or fixed;
- missed signals fixed or assigned;
- validation plan;
- next review date.

## Stop conditions

Escalate before tuning if:

- critical alert route is unavailable;
- primary and backup owners are unavailable;
- readiness or health alerts are disabled;
- protected route anomaly alert is disabled;
- threshold change would hide critical failures;
- workflow gate bypass is requested;
- evidence includes secret values.

## Guardrails

- No alert disablement without owner approval.
- No threshold change that hides critical failures.
- No automatic approval.
- No workflow gate bypass.
- No secret values in evidence.
- No private runtime values in notes.
- No publishing.
- No scheduling.
- No rendering.
- No external export.

## Validation

Covered by:

```text
tests/integration/test_p11_step_02.py
```

The validation checks source references, alert inventory, threshold review, noisy and missed signal review, outputs, stop conditions, and guardrails.
