Feature: FR acceptance contract
  Scenario: The canonical ledger preserves and attributes approved scenarios
    Given an open FR has an agreed behavior scenario
    When the intake agent records the approved scenario through the FR CLI
    Then the ledger preserves its Given When Then values and intake provenance