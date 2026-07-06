Feature: Phase 0 risk controls
  Publish-mode output must pass the foundation controls.

  Scenario: Candidate assets cannot be used for publish output
    Given a publication package references candidate media
    When the gate checks the package
    Then the package requires approved evidence before publish

  Scenario: Expired license coverage fails publish validation
    Given an asset has expired or out-of-scope coverage
    When publish mode is requested
    Then the gate records a failed decision

  Scenario: Preview render output is non-publishable
    Given a render manifest is generated in preview mode
    When it is selected for a publish package
    Then publication validation rejects it

  Scenario: Publish manifests require approval, evidence, and stable hashes
    Given a publish manifest references assets and render outputs
    When publish validation runs
    Then approval, evidence links, asset hashes, and manifest hashes are required

  Scenario: Unapproved voices and missing consent fail validation
    Given narration uses an unapproved voice or missing consent evidence
    When publish narration validation runs
    Then the narration output is rejected

  Scenario: Generated media requires provider lineage
    Given generated media is included in a publish manifest
    When manifest validation runs
    Then provider request, response, parent asset, output hash, and evidence lineage are required

  Scenario: Quality gate rejects placeholders and unsafe publish output
    Given a package contains placeholders, missing disclosure, or failed quality findings
    When the quality gate evaluates the package
    Then publish mode is rejected or escalated for review
