# P35 Step 01

Part of #451. Closes #452 after the batch PR merges.

## Goal

Implement deterministic local checksum generation for artifact payloads and file-like content.

## Behavior

- Supports `sha256` checksums.
- Supports text payloads.
- Supports bytes payloads.
- Supports JSON-serializable payloads.
- Normalizes JSON before hashing.
- Returns algorithm, digest, byte count, content type, and generated time metadata.

## Runtime helper

```text
src/p35_integrity.py
```

## Safety boundary

Checksum generation is local and side-effect free. It does not read remote files, upload checksums, sign content, or manage keys.
