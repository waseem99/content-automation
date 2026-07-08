# P12 Step 03

This step documents operational KPI reporting for production lifecycle governance.

Part of #170. Closes #173 after the PR merges.

## Goal

Create a recurring operational KPI report that turns production review, alert, incident, access, release, and evidence data into governance-ready operating signals.

## Source references

This runbook builds on:

```text
docs/operations/p12-step-01.md
docs/operations/p12-step-02.md
docs/operations/p11-step-01.md
docs/operations/p11-step-02.md
docs/operations/p11-step-03.md
docs/operations/p11-step-04.md
```

## Reporting cadence

- Publish a monthly operational KPI summary.
- Review critical KPI breaches during weekly rollout review.
- Include access review findings during the quarterly reporting cycle.
- Archive KPI evidence before P12 closeout.

## KPI categories

Required KPI categories:

- release governance;
- production health;
- alert quality;
- incident response;
- incident closure;
- access review;
- evidence archive completeness;
- owner coverage;
- exception aging;
- audit control readiness.

## KPI fields

Each KPI must record:

- KPI name;
- owner;
- reporting period;
- target;
- actual value;
- status;
- source evidence;
- trend note;
- corrective action if needed;
- next review date.

## Minimum KPI set

Minimum report entries:

- releases completed within approved window;
- release windows blocked by stop condition;
- critical alerts routed successfully;
- noisy alerts accepted or fixed;
- incidents reviewed within cadence;
- critical incident actions closed on time;
- quarterly access review completion;
- access removals completed on time;
- evidence entries with complete index fields;
- open exceptions past review date.

## Review decisions

Allowed decisions:

- continue current operating posture;
- open corrective action;
- escalate KPI breach;
- request release hold;
- request access review follow-up;
- request alert tuning follow-up;
- request incident review follow-up;
- accept documented risk with owner and expiry date.

## Evidence requirements

Every KPI report must include:

- reporting period;
- owner list;
- source evidence links;
- action item list;
- accepted risks;
- review decision;
- archive entry.

## Stop conditions

Stop report closure if:

- KPI owner is missing;
- source evidence is missing;
- critical breach has no action owner;
- accepted risk has no expiry date;
- report includes secret values;
- workflow gate bypass is requested.

## Guardrails

- No KPI report closure without source evidence.
- No critical breach without action owner.
- No accepted risk without expiry date.
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
tests/integration/test_p12_step_03.py
```

The validation checks source references, cadence, KPI categories, KPI fields, minimum KPI set, review decisions, evidence requirements, stop conditions, and guardrails.
