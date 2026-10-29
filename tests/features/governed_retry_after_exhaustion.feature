Feature: Governed retry after exhaustion
  Scenario: Reject an exhausted retry recovery without approval or reason
    Given a failed TODO exhausted its retry budget
    When the operation is called without explicit approval or a reason
    Then it rejects and leaves state and history unchanged

  Scenario: Grant one audited additional attempt
    Given a failed TODO exhausted its retry budget and has no prior manual grant
    When an authorized operator approves one extra attempt with a reason
    Then it transitions to queued and appends an audit event with actor, reason, and attempt transition while preserving the original configured retry policy

  Scenario: Reject a second recovery after the manual grant is used
    Given the one-time manual grant has been used and the added attempt later fails
    When another recovery is requested
    Then it rejects without changing state or history

  Scenario: Reject recovery while a lease is active
    Given a TODO is claimed or running
    When recovery is requested
    Then it rejects without changing state or revoking its lease