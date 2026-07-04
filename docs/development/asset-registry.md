# Canonical Asset Registry

The registry assigns each file a stable asset ID linked to a SHA-256 calculated from the file bytes. It supports source files, derivatives, generated outputs, evidence files, voices, music, fonts, and renders.

The registry does not grant publication approval. Approval and publish checks are separate controls.

## Storage modes

`workspace:///...` references a file that remains under the configured workspace root.

`managed:///...` references a content-addressed copy under the managed asset store. Evidence files and preserved source-image bytes use this mode.

## Backfill

Inspect existing files without database writes:

    python -m src.commands.assets backfill --root data --dry-run

Commit the result:

    python -m src.commands.assets backfill --root data --commit

Verify a previously registered tree:

    python -m src.commands.assets verify --root data

The command excludes its own reports, sidecars, cache directories, repository metadata, and managed storage.

## Extraction runs

Register an existing extraction manifest:

    python -m src.commands.assets register-run --manifest data/output/run/manifest.json

The database operation registers the source and clips together. The manifest is updated only after the transaction succeeds.

## Classification defaults

- Source match videos and extracted clips are internal-only.
- Web images and their normalized derivatives are candidates.
- Evidence files are internal-only canonical evidence assets.
- Generated voice and image outputs are candidates.
- Preview renders are internal-only.

Search filters and source metadata never create an approval decision.

## Verification

Asset resolution checks that the registered storage location exists and recalculates the hash before returning the path. Missing, expired, deleted, or modified assets fail closed.
