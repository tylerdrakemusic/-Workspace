Feature: Pinned skill source integrity

  Scenario: A CRLF checkout matching the pinned LF blob allows the prewrite gate
    Given the committed LF skill is checked out with CRLF and the target matches the pinned content
    When the skill verifier runs before the write
    Then the result is source_match and the prewrite gate allows the write

  Scenario: A missing pinned blob or mismatched source SHA fails closed
    Given pinned-source fixtures have a missing blob and an incorrect source SHA
    When the skill verifier runs before the write
    Then both pinned-source failures block the write

  Scenario: Genuine target content drift blocks the write
    Given a valid pinned source exists but the target differs from source and manifest
    When the skill verifier runs before the write
    Then the result reports integrity_failure and blocks the write

  Scenario: An unpinned source keeps live-file comparison behavior
    Given an unpinned live source differs from the manifest-matching target
    When the skill verifier runs before the write
    Then the result reports local_customization without a hard finding

  Scenario: Full integrity verification still checks agent prompts and pinned skills
    Given a tracked agent prompt has an unapproved prompt-injection edit and the pinned skill source is valid
    When the full integrity verifier runs
    Then the agent manifest rejects the edit and the pinned source still reports source_match