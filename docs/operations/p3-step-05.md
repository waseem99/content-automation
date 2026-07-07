# P3 Step 05

This step generates a deterministic delivery manifest from a final-approved P3 package.

## Flow

1. P3 step three creates a package row.
2. P3 step four approves the package through the final package gate.
3. `P3DeliveryManifestService.create_for_package` requires the approved package.
4. The worker builds deterministic manifest content from package data, lineage, selected options, and final approval metadata.
5. The service stores a manifest row with hash, package linkage, lineage refs, approval metadata, package metadata, and stage execution ID.

## Service method

- `create_for_package(workflow_run_id, package_id, actor)`

## Stored manifest content

- workflow run id
- package id
- step plan id
- package hash
- selected option ids
- selected asset ids alias
- package stage execution id
- scene map
- final approval status

## Guardrails

- Missing final package approval blocks manifest creation.
- Pending or returned package approval blocks manifest creation.
- Wrong-workflow packages fail closed.
- Duplicate manifest requests reuse the existing worker output and manifest row.
- This step does not publish, schedule, or render anything.

## Next step

P3-06 should expose operator delivery tooling for package and manifest status.
