# P29 Step 05

Part of #331. Closes #366 after the batch PR merges.

## Goal

Define what evidence should be captured when a human approves, blocks, or requests revision on a generated content package.

## Required evidence fields

- `reviewer`
- `decision`
- `timestamp`
- `reviewed_package_version`
- `blockers`
- `required_changes`
- `source_risk_notes`
- `approval_scope`

## Decision examples

Evidence trail examples cover:

- `approved`
- `blocked`
- `revisions_required`

## Privacy and safety rules

Evidence is internal and not a platform upload artifact.

Do not store:

- secrets;
- customer data;
- unnecessary external account details;
- platform credentials.

## Publish-readiness connection

Each evidence record should connect back to the publish-readiness manifest so operators can see what decision supported or blocked the current readiness state.

## Example

```text
docs/operations/p29-editorial-evidence-example.json
```

## Validation

```text
src/p29_governance.py
tests/integration/test_p29_batch_02_06.py
```

## Stop conditions

Stop if a future change attempts to:

- implement authentication/authorization in this step;
- implement a permanent audit database in this step;
- store secrets or customer data;
- treat evidence as platform upload permission;
- set `publish_allowed` to `true`;
- bypass human/legal/editorial judgment.
