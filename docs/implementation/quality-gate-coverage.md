# Publish Quality Gate Coverage

Issue #6 separates render completion from publication permission. A render job can finish successfully while the publication package remains unavailable.

## Automated coverage

| Scenario | Coverage |
| --- | --- |
| Match footage rights | Rights gate, manifest, and quality code checks. |
| Platform-specific rights | Rights gate and manifest regressions. |
| Expired licence | Rights gate regressions. |
| Web image approval | Rights gate and manifest regressions. |
| Attribution | Rights approval plus quality disclosure propagation. |
| Voice approval | Voice media policy regressions. |
| Background music | Voice/media and rights regressions. |
| Publish placeholders | Manifest builder and quality manifest checks. |
| Preview output | Manifest runtime plus publication package trigger. |
| Source and derivative preservation | Provider lineage regressions. |
| Stale asset bytes | Quality hash regression test. |
| Frame-one hook | Manifest preset and runtime regressions. |
| Package requires quality report | Quality package guard tests and database trigger. |

## Review mapping

Caption, safe-area, and audio-track findings return `human_review_required`. A package is not created until a later report permits publication.

## Database enforcement

The publication package trigger requires a publish manifest, a succeeded render job with output, and a matching report whose status is `pass` or `pass_with_disclosure`.
