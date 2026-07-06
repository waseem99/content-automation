# Provider Lineage Backfill Strategy

Issue #5 requires generated and transformed assets to remain traceable to their source asset, provider operation, prompt/configuration and output bytes.

## Rules for new work

- Never overwrite or delete the original source file when creating a derivative.
- Register each derivative as a new asset with `parent_asset_id`.
- Record a succeeded provider call before registering generation evidence.
- Record provider, operation, model, provider request ID, request fingerprint, response fingerprint, input hash and output hash.
- Do not store secrets or raw API keys in provider metadata.
- Publish manifests cannot include AI-generated assets unless provider-generation evidence exists.
- Derivative generation must pass source-rights checks for modification and synthetic-edit permission before registration.

## Backfill existing production folders

1. Identify source files already registered in `football_brief.assets`.
2. For each generated output, compute SHA-256 and locate the closest source/parent asset.
3. Register the output as a new `ai_generated` asset with `parent_asset_id`.
4. Create or recover the associated provider call from local logs.
5. Reconstruct request/response fingerprints from non-secret prompt/configuration and output hash.
6. Insert provider-generation evidence only when the parent hash and output hash can be proven.
7. Leave ambiguous files as `candidate` or `internal_only`; do not mark them publishable.
8. For repeated identical requests, prefer the existing evidence row and output asset rather than creating duplicates.

## Unknown history

When a provider request ID, prompt hash, or parent hash cannot be reconstructed, do not fabricate evidence. Keep the asset out of publish manifests until reviewed and regenerated through the new lineage service.
