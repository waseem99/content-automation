Feature: Phase 0 acceptance

  Scenario: Package requires approval
    Given a package exists
    When validation runs
    Then approval is required
