Feature: Phase 1 platform foundation
  Workflows must be reproducible, auditable, resumable, idempotent, budget-controlled, and safe for human review.

  Scenario: Start a versioned workflow run
    Given a content item exists
    When the operator starts workflow "football_brief_mvp" version "1.0"
    Then a workflow run is created with status "active"
    And its input hash, approved budget, workflow version, creator, and timestamp are stored
    And a workflow event records the transition

  Scenario: Reject duplicate workflow identity
    Given a workflow run already exists for the same content item, workflow name, version, and input hash
    When the same workflow is started again
    Then the existing run is returned or an explicit duplicate result is returned
    And a second billable workflow is not created

  Scenario: Execute a worker with an idempotency key
    Given a stage worker has a deterministic idempotency key
    And the provider call for that key already succeeded
    When the stage is retried with identical inputs
    Then the saved successful result is reused
    And no duplicate provider charge is created

  Scenario: Retry a failed stage without overwriting history
    Given stage attempt 1 failed
    When an authorized retry is requested
    Then stage attempt 2 is created
    And attempt 1 remains unchanged
    And the workflow event stream records the retry reason and actor

  Scenario: Resume after recoverable failure
    Given a workflow is blocked because one provider call failed
    And all earlier stages completed successfully
    When the provider problem is resolved and the workflow is resumed
    Then only the failed or invalidated stage and its dependants rerun
    And completed valid stages are reused

  Scenario: Invalidate stale downstream outputs
    Given a completed script stage produced an output hash
    And an approved script revision changes that hash
    When the workflow resumes
    Then storyboard, asset plan, voice, render manifest, and render outputs are marked stale or superseded
    And they cannot be used for publication until regenerated and approved

  Scenario: Require human approval at a gated stage
    Given a stage is configured to require human approval
    When the automated worker completes
    Then the stage enters "awaiting_human"
    And the workflow does not advance
    When a reviewer records "approved" with rationale
    Then the approval, reviewer, checklist, and timestamp are stored
    And the workflow may advance

  Scenario: Preserve rejection and revision history
    Given a reviewer requests changes to a stage
    When a revised stage output is submitted
    Then the original review and output remain immutable
    And a new stage attempt or version is created

  Scenario: Enforce workflow budget
    Given the workflow has an approved budget of 5.00 USD
    And recorded actual cost is 4.90 USD
    When a worker estimates a further cost of 0.25 USD
    Then the stage does not call the provider
    And the stage enters "awaiting_human" or "blocked"
    And the reason includes "BUDGET_EXCEEDED"

  Scenario: Reconcile provider cost records
    Given a provider call succeeds
    When usage and cost are returned
    Then the provider request ID, units, unit name, cost, stage, and workflow are recorded
    And workflow actual cost equals the sum of its cost entries

  Scenario: Store media by asset ID rather than arbitrary path
    Given a worker requests an input media file
    When the input is resolved
    Then it is resolved from a registered asset ID and authorized storage URI
    And direct unregistered filesystem paths are rejected in publish workflows

  Scenario: Protect secrets and sensitive payloads
    Given a provider request uses an API key
    When logs, provider calls, workflow outputs, and errors are stored
    Then the API key is absent
    And configured secret patterns are redacted
    And raw private provider payloads are not persisted unless explicitly approved

  Scenario: Create an immutable publish render manifest
    Given the script, storyboard, brand, policy, voice, music, assets, and rights are approved
    When a publish manifest is created
    Then its complete canonical JSON is hashed
    And the hash is unique and immutable
    And every referenced asset stores its expected file hash and rights record

  Scenario: Reject render manifest mutation
    Given a publish render manifest has been approved
    When a caller attempts to modify its JSON or approvals
    Then the modification is rejected
    And a new manifest version must be created instead

  Scenario: Record every state transition
    Given a workflow moves between statuses or stages
    Then an append-only workflow event records the prior state, new state, actor, reason, and timestamp

  Scenario: Generate a complete audit report
    Given a publish render has completed
    When an auditor requests the workflow evidence
    Then the report includes the workflow version, stage attempts, human reviews, provider calls, costs, asset rights, render manifest, quality report, and operator actions

  Scenario: Block publication without a passing quality report
    Given a publish render job succeeded technically
    But its latest quality report is "block" or "human_review_required"
    When a publication package is requested
    Then the package is not created
