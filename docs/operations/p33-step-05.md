# P33 Step 05

Part of #435. Closes #440 after the batch PR merges.

## Goal

Add operator-facing CLI usage examples and runbook notes for the safe local runtime.

## Safe examples

```bash
python -m src.p33_cli_runtime validate-package --input content_package.json --mode validate
python -m src.p33_cli_runtime review-readiness --input publish_readiness_manifest.json --mode inspect
python -m src.p33_cli_runtime build-report --input reporting_input_bundle.json --mode build-local-artifact
python -m src.p33_cli_runtime export-handoff --input operator_report_package.json --mode package-local-handoff
python -m src.p33_cli_runtime dry-run-publish-check --input publish_readiness_manifest.json --input risk_report.json --mode validate
python -m src.p33_cli_runtime closeout-check --input closeout_checklist.json --mode validate
```

## Blocked examples

```bash
python -m src.p33_cli_runtime validate-package --mode upload
python -m src.p33_cli_runtime dry-run-publish-check --allow-upload
python -m src.p33_cli_runtime build-report --allow-network
```

## Runbook notes

Operators must treat output as local dry-run guidance only. The runtime must not be used for publishing, uploads, scheduling, notifications, account sync, credential handling, or destructive cleanup.
