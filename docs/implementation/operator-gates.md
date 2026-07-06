# Operator Gates

Issue #10 adds auditable operator gates for rights, scripts, manifests, compliance, quality and stage-level decisions.

## Flow

- Create a gate request for a workflow, stage, or target object.
- A running stage tied to the request moves to `awaiting_human` through the workflow state machine.
- A reviewer records a decision with identity, rationale and checklist.
- The decision row is append-only.
- The request is closed as decided.

## Stage mapping

| Decision | Stage result |
| --- | --- |
| approved / pass / pass_with_disclosure | completed |
| changes_requested | needs_revision |
| rejected / block | rejected |
| human_review_required | stays awaiting_human |

## Safeguards

- Reviewer identity is mandatory.
- Rationale is mandatory.
- Checklist is mandatory.
- Request creator cannot decide their own gate when configured.
- Positive decisions cannot pass a blocking rights or quality result.
- Revisions use the existing retry path, preserving prior stage evidence.
