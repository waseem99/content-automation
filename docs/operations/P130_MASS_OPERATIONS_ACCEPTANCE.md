# P130 Mass Operations Acceptance

Creator Studio remains database-native and uses only Super Admin, Admin and Reviewer public roles. Reviewers inherit production capabilities only within their assigned brands.

## Full acceptance gate

The workflow creates 1,000 campaign items sharing one exact grouped hard blocker, then proves:

- an assigned Reviewer can create an immutable database selection snapshot;
- an unassigned Reviewer is rejected for the same campaign;
- the snapshot contains exactly 1,000 stable member identities and a SHA-256 digest;
- one background retry job retains exactly 1,000 item result rows;
- every eligible run becomes queued and every item becomes auto-progressing;
- all 1,000 grouped exceptions are superseded with one audited action;
- no individual item page or spreadsheet is required;
- one inline edit succeeds using the exact item `updated_at` value;
- a second edit using the stale value is rejected by optimistic locking.

The existing P121 grid separately proves cursor-backed query, search, filtering and grouping at 20,000-row scale. P130 supplies the remaining durable mass-action and inline-edit evidence.
