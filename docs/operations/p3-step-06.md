# P3 Step 06

This step exposes operator tooling for P3 review and delivery status.

## Queue visibility

`operator queue` now surfaces:

- `p3_option_review` items for options with missing, pending, or returned review status.
- `package_review` items for packages with missing, pending, or returned final review status.
- Existing P2 queue items remain available.

## CLI commands

Option review:

```bash
python -m src.infrastructure.database.cli operator request-option --workflow-run-id <workflow-id> --option-id <option-id> --json
python -m src.infrastructure.database.cli operator approve-option --workflow-run-id <workflow-id> --option-id <option-id> --reviewed-by <name> --json
```

Package review:

```bash
python -m src.infrastructure.database.cli operator request-package --workflow-run-id <workflow-id> --package-id <package-id> --json
python -m src.infrastructure.database.cli operator approve-package --workflow-run-id <workflow-id> --package-id <package-id> --reviewed-by <name> --json
python -m src.infrastructure.database.cli operator package-status --workflow-run-id <workflow-id> --package-id <package-id> --json
```

Manifest status:

```bash
python -m src.infrastructure.database.cli operator manifest-status --workflow-run-id <workflow-id> --json
python -m src.infrastructure.database.cli operator manifest-status --workflow-run-id <workflow-id> --package-id <package-id> --json
```

## Guardrails

- Commands remain explicit and review-driven.
- Option approval is still handled through the P3 option review service.
- Package approval is still handled through the final package review gate.
- Status commands do not mutate state.
- Manifest status only reads existing manifest rows.
- This step does not publish, schedule, render, or export externally.

## Validation

Covered by `tests/integration/test_p3_step_06.py` through the P3 wildcard entry in the P1 Acceptance Harness.
