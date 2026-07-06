# Test Fixture Policy

Golden fixtures used by the acceptance harness must be safe to commit and safe to use in CI.

## Allowed sources

- `owned_by_project`: created by the project team.
- `public_domain`: public-domain material with source and retrieval date recorded.
- `explicit_license`: material with license terms recorded.
- `generated_safe`: synthetic content made from simple shapes, text, or generated primitives.

## Required fields

Each committed media fixture must have a row in `tests/fixtures/provenance.json` with:

- repository path;
- purpose;
- source type;
- license status;
- creator or source;
- creation or retrieval date;
- SHA-256 hash;
- notes explaining why the fixture is safe.

## Not allowed

- Unknown-origin media.
- Broadcast clips or match footage without recorded permission.
- Person likenesses without recorded permission.
- Brand logos, music, fonts, or screenshots without recorded coverage.
- Temporary local files copied into the repository without provenance.

Any new fixture must update provenance in the same PR. The acceptance harness fails if a golden fixture is missing provenance or if its hash changes silently.
