Feature: FR acceptance contract
  Scenario: The canonical ledger preserves and attributes approved scenarios
    Given scope approval is recorded for a triaged FR with an agreed behavior scenario
    When the intake agent records the approved scenario through the FR CLI
    Then the ledger preserves its Given When Then values and intake provenance