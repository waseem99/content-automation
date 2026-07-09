# P35 Step 05

Part of #451. Closes #456 after the batch PR merges.

## Goal

Implement drift and warning report semantics for local artifact inventories without cleanup or destructive actions.

## Warning types

- missing artifacts detected;
- changed artifacts detected;
- unexpected artifacts detected;
- stale retention review;
- manual review required.

## Operator guidance

The report can recommend advisory next steps only. Operators must not delete, move, upload, sync, or publish from this report.

## Safety boundary

No cleanup, deletion, movement, upload, cloud sync, scheduler, network call, or automated remediation is performed.
