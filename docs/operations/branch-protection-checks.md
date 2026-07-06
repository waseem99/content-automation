# Branch Protection Check Recommendations

For the `test` integration branch, require these checks before merge:

- P1 Acceptance Harness
- P1 PostgreSQL Foundation
- P1 Worker Contracts
- P1 Workflow State
- P1 Human Review
- P1 Budget Controls
- P1 Ops Storage
- P0 Canonical Asset Registry
- P0 Rights Gate
- P0 Render Manifests
- P0 Voice Media Policy
- P0 Provider Lineage
- P0 Quality Gate

Recommended branch settings:

- Require pull requests before merge.
- Require the latest branch head to pass checks.
- Require conversations to be resolved.
- Restrict direct pushes to `test`.
- Prefer squash merges for issue-sized implementation branches.
- Do not mark a draft PR ready until the acceptance harness and related P0/P1 workflows are green.
- Merge only with the exact validated head SHA.
