# P89 Script, Claim Evidence, and Source Review

## Purpose

P89 turns an approved concept-stage content item into an exact, reviewable script version before narration or preview generation. Script text, scene plan, claims, sources, links, review actions, and decisions are retained as evidence.

## Safe default

The default generator is deterministic and fixed-seed. The optional local model adapter accepts loopback endpoints only and falls back to deterministic generation when local output fails validation. No paid-provider path is included.

Generated factual claims start as `needs_source`. They are visible to reviewers and can be submitted for review, but they cannot be approved until supported by a source linked as direct or corroborating evidence.

## Operator flow

1. A producer initializes a script from content whose production workflow is at `script_draft`.
2. The producer edits the working version, scene plan, claims, and source pack using optimistic document locking.
3. Submission seals the exact version and all child evidence.
4. A reviewer creates version-bound inline, factual, source, tone, or general actions.
5. Review actions can be resolved exactly once and remain attached to the original version.
6. An independent reviewer records one exact-version decision.
7. `changes_requested` or `rejected` versions remain immutable. A producer creates an immediate working child that copies the complete script, scene, claim, source, and support graph. Prior actions and decisions remain on the parent.
8. Approval succeeds only when the exact submitted version satisfies every approval gate.

## Approval gates

PostgreSQL blocks approval when any of the following is true:

- section word counts or duration totals differ from the version summary;
- estimated narration duration exceeds the configured tolerance;
- any script section lacks a scene-plan entry;
- any non-CTA narration paragraph lacks a claim mapping;
- any factual claim is not marked supported;
- a supported factual claim lacks a direct or corroborating source link;
- an inline edit, factual query, source request, or tone-change action remains unresolved;
- the review decision targets a stale version, uses a stale document lock, or is made by the last editor.

## Downstream gate

New `narration` and `preview` generation jobs must include `input_payload.script_version_id`. PostgreSQL accepts the job only when:

- the script version is the document's current version;
- the version is approved;
- it belongs to the same content item;
- its basis content version equals the job's content version;
- at least one scene-plan entry exists.

A missing, stale, rejected, changed, or mismatched script version cannot enter narration or preview work.

## Roles

- Producer: initialize, edit, update sources, submit, resolve assigned review actions, and create revisions for assigned brands.
- Reviewer: create review actions, resolve review actions, and decide exact submitted versions for assigned brands.
- Administrator: full brand visibility and review authority, while independent-review checks still apply.
