# P29 Step 02

Part of #331. Closes #363 after the batch PR merges.

## Goal

Create a simple human review checklist operators can use before approving generated football content for export or publishing handoff.

## Required checklist sections

- `script_accuracy`
- `hook_strength`
- `title_thumbnail_alignment`
- `asset_rights`
- `image_attribution`
- `music_license`
- `captions`
- `factual_sources`
- `originality`
- `platform_fit`

## Review states

Each checklist section uses:

- `pass`
- `fail`
- `needs_revision`

Any `fail` blocks approval. Any `needs_revision` returns the package to `revisions_required`.

## Format variants

The checklist includes variants for:

- `shorts`
- `explainer`

Shorts checks focus on first-two-second hook strength, mobile readability, captions, and platform fit. Explainer checks focus on chapter logic, factual density, source context, and asset clarity.

## Operator scope

This checklist is intentionally simple for non-engineer operators. It supports human review only and does not automate approval or legal clearance.

## Example

```text
docs/operations/p29-human-review-checklist-example.json
```

## Validation

```text
src/p29_governance.py
tests/integration/test_p29_batch_02_06.py
```

## Stop conditions

Stop if a future change attempts to:

- automate approval;
- claim legal clearance;
- skip rights review;
- skip source attribution;
- set `publish_allowed` to `true`;
- upload or publish content directly.
