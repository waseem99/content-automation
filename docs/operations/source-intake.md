# Source Intake CLI

P2-01 adds a controlled intake path for football topics and references.

## Create topic intake

```bash
python -m src.infrastructure.database.cli intake create --workflow-run-id <id> --topic "Derby preview" --created-by operator
```

## Create reference-backed intake

```bash
python -m src.infrastructure.database.cli intake create --workflow-run-id <id> --url "https://example.com/story" --created-by operator --json
```

## List workflow intakes

```bash
python -m src.infrastructure.database.cli intake list --workflow-run-id <id> --json
```

## Guardrails

- Topic or URL is required.
- Only web URLs are accepted.
- Local paths are rejected.
- Duplicate payloads reuse the existing canonical record.
- Create and reuse actions emit workflow events.
