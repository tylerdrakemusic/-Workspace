Feature: FR acceptance contract
  Scenario: The canonical ledger preserves an agreed Given When Then scenario
    Given an open FR has an agreed behavior scenario
    When the scenario is recorded as acceptance criteria through the FR CLI
    Then the ledger preserves its Given When Then values