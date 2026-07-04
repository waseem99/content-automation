Feature: Phase 0 risk containment
  Publishable media must fail closed when rights, voice, music, disclosure, or visual requirements are unresolved.

  Background:
    Given the system is running in "publish" mode
    And all decisions are recorded against a workflow run

  Scenario: Block an extracted match clip without approved rights
    Given a video asset originated from extracted broadcast footage
    And its lifecycle status is "internal_only"
    And it has no approved rights record for YouTube commercial use
    When a publish render manifest is validated
    Then validation returns "BLOCK"
    And the reason includes "UNAPPROVED_MATCH_FOOTAGE"
    And no render job is created

  Scenario: Permit a clip with complete platform-specific rights
    Given a video asset has an approved rights record
    And commercial use is allowed
    And modification is allowed
    And YouTube is included in the approved platforms
    And the licence is not expired or revoked
    And supporting rights evidence exists
    When a publish render manifest is validated for YouTube
    Then the asset passes the rights gate

  Scenario: Block an expired licence
    Given an asset has an approved rights record whose expiry is in the past
    When a publish render manifest is validated
    Then validation returns "BLOCK"
    And the reason includes "RIGHTS_EXPIRED"

  Scenario: Block a web image discovered through search but not approved
    Given an image candidate was discovered through a search provider
    And its source URL and dimensions are stored
    But no rights reviewer has approved its commercial use
    When the image is added to a publish render manifest
    Then validation returns "BLOCK"
    And the reason includes "RIGHTS_NOT_APPROVED"

  Scenario: Require attribution when the licence requires it
    Given an asset rights record requires attribution
    And the attribution text is empty
    When rights approval is attempted
    Then approval is rejected
    And the reason includes "ATTRIBUTION_MISSING"

  Scenario: Reject an unauthorized cloned voice
    Given a provider voice is classified as "cloned"
    And no consent evidence asset is attached
    When the voice is approved
    Then approval is rejected
    And the voice cannot be used in a publish render

  Scenario: Permit an approved premade narrator
    Given a premade provider voice is approved
    And the requested language and platform are permitted
    And the approval is not expired or revoked
    When a publish manifest references the voice
    Then the voice policy gate passes

  Scenario: Block unapproved background music
    Given a music asset has no approved rights record for the requested platform
    When a publish manifest references the music asset
    Then validation returns "BLOCK"
    And the reason includes "MUSIC_RIGHTS_NOT_APPROVED"

  Scenario: Block placeholders in publish mode
    Given a storyboard shot has no resolved asset
    And the renderer would otherwise insert a placeholder
    When a publish render is requested
    Then validation returns "BLOCK"
    And the reason includes "PLACEHOLDER_ASSET"

  Scenario: Permit watermarked placeholders only in preview mode
    Given the system is running in "preview" mode
    And a storyboard shot has no resolved asset
    When a preview render is requested
    Then a visibly watermarked placeholder may be used
    And the output is marked "NOT_FOR_PUBLICATION"
    And no publication package can reference that output

  Scenario: Preserve original and derived assets
    Given an approved source image is edited by an AI or image-processing provider
    When the derived image is stored
    Then the source asset remains unchanged
    And the derived asset references its parent asset
    And the provider, operation, prompt version, and output hash are recorded

  Scenario: Prevent a changed asset from using stale approval
    Given a render manifest references an approved asset hash
    And the file bytes later change
    When the render manifest is validated
    Then validation returns "BLOCK"
    And the reason includes "ASSET_HASH_MISMATCH"

  Scenario: Remove the pre-hook intro
    Given a short-form render starts
    When the first frame is inspected
    Then editorial content begins at frame one
    And any logo sting begins only after or within the hook
    And the logo sting is no longer than 0.7 seconds
