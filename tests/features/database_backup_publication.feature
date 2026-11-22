Feature: Verified database backup publication
  Scenario: Invalid SQLCipher output preserves the previous recovery generation
    Given a valid recovery generation and synthetic approved backup sources
    When the copied workspace FR ledger SQLCipher artifact is corrupted
    Then the backup fails without publishing success and retains the prior recovery generation

  Scenario: A checksum mismatch cannot publish success or prune recovery
    Given a valid recovery generation and synthetic approved backup sources
    When a copied Workspace database is corrupted during publication
    Then the backup fails without publishing success and retains the prior recovery generation

  Scenario: An exFAT-like directory rename cannot corrupt approved artifacts
    Given healthy synthetic sources for every approved manifest entry
    When the scheduled backup runner publishes a generation on an exFAT-like volume
    Then every approved artifact is hash-valid and every SQLCipher artifact passes integrity checks

  Scenario: A complete approved manifest is published only after validation
    Given healthy synthetic sources for every approved manifest entry
    When the scheduled backup runner publishes a generation
    Then every approved artifact is hash-valid and every SQLCipher artifact passes integrity checks