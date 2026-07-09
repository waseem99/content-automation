# P34 Step 03

Part of #443. Closes #446 after the batch PR merges.

## Goal

Implement a local operator summary writer that materializes Markdown summaries for human review.

## Summary content

- command name;
- status;
- mode;
- warnings;
- blockers;
- planned outputs;
- guardrail text.

## Runtime helpers

```text
build_operator_summary(...)
write_operator_summary(...)
```

## Safety boundary

The summary is local-only and review-required. It is not emailed, posted to Slack, converted to HTML/PDF, uploaded externally, or published.
