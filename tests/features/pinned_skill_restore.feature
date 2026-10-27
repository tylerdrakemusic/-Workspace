Feature: One-target pinned skill restoration

  Scenario: The configured Humanizer pin and manifest hash agree
    Given the configured Humanizer pin and manifest hash agree
    When the explicit one-target restore runs
    Then only the installed target is restored and its SHA matches the existing pin and manifest

  Scenario: Invalid or ambiguous pinned restore inputs fail before changing any file
    Given the pinned blob, SHA, target mapping, or manifest entry is invalid or ambiguous
    When restore is requested
    Then it fails before changing any file

  Scenario: Successful restore passes canonical verification with temporary quarantine
    Given the restore succeeds
    When canonical verification runs
    Then no local manifest mismatch remains; unrelated external source updates remain quarantined only for that verification run