Feature: Workspace advisory mypy report
  Scenario: Workspace pilot reports findings without failing CI
    Given the Workspace pilot module scope is selected from its existing configuration, tests, and CI conventions
    When advisory mypy runs
    Then it reports findings for that scope without failing CI, and pytest remains the required quality gate