Feature: Cross-project CI uses the producer pull request revision
  Scenario: Consumer CI checks out the producer pull request head
    Given the producer branch head is available
    When consumer CI resolves the producer peer revision
    Then it checks out the exact producer head before behavior tests

  Scenario: Missing producer branch is treated as an unpaired consumer PR
    Given the consumer pull request has no matching producer branch
    When consumer CI resolves a missing producer branch
    Then it uses peer main for the unpaired consumer PR

  Scenario: Concurrent QA proof writes remain serialized and readable
    Given an isolated QA run needs to record two proof artifacts
    When the QA workflow starts overlapping proof CLI writers
    Then both writes succeed and each proof is readable from the report

  Scenario: Coordination subprocess failures identify their failing layer
    Given the coordination FR CLI subprocess seam is available
    When setup, timeout, and CLI operation failures occur
    Then each failure is reported as its own category

  Scenario: FR CLI child does not inherit MCP protocol stdin
    Given the coordinator request leaves its stdio input pipe open
    When the coordinator launches a CLI child that reads stdin
    Then the child receives EOF and completes before its deadline

  Scenario: Weekly SCAN tolerates an identical completed TODO
    Given an identical completed SCAN TODO exists
    When the weekly integrity scan runs
    Then it reuses the completed TODO and finishes without duplicate rows

  Scenario: Pre-write verification allows clean sources and blocks confirmed mismatch
    Given a project has clean declared external skill sources
    When the pre-write security gate verifies the project and a confirmed mismatch
    Then clean integrity passes and confirmed mismatch blocks the write

  Scenario: Pre-write verification fails open on operational error
    Given the canonical verifier encounters an operational error
    When the pre-write security gate evaluates that failure
    Then the write remains allowed and a warning is emitted