Feature: New-FR deterministic boundaries
  Scenario: Agent-facing workflow CLI contracts are executable
    Given the five shared workflow CLI entry points are selected
    When each entry point is invoked with --help
    Then each exits successfully and exposes its stable handoff contract

  Scenario: Agent role tiers do not pin a host model across project paths
    Given agent definitions across all six project paths are loaded
    When the host resolves representative complexity tiers
    Then agent frontmatter has no model pin and all role tiers remain available

  Scenario: The named Quantum model selector is absent
    Given the session and subagent hook configuration is inspected
    When the obsolete model selector registration and script are checked
    Then neither the registration nor selector script is present

  Scenario: An unrelated soaking FR does not block implementation
    Given one local FR is soaking and an unrelated FR is branched
    When the canonical FR CLI advances the branched FR to implementation
    Then the implementation FR advances and the unrelated FR stays soaking

  Scenario: The merge CLI requires final approval for the linked PR set
    Given a local FR ledger has an architecture-reviewed FR in automated review
    When the canonical FR CLI requests a merge
    Then the ledger rejects the merge and preserves the automated-review state

  Scenario: A pending cost outcome blocks an approved FR from merging
    Given an architecture-reviewed FR is Tyler-approved with pending cost
    When the canonical FR CLI requests a merge for the pending-cost FR
    Then the merge is rejected and the FR remains Tyler-approved