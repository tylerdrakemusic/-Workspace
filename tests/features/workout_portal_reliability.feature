Feature: Workout portal service reliability
  The resident Workspace supervisor owns Workout startup, health checks,
  recovery, and portal-visible status.

  Scenario: Workout is registered from the primary Life checkout
    Given the portal service manifest
    When I resolve Workout's configured launch contract
    Then Workout launches from the primary Life checkout on its loopback health endpoint
    And the existing Music service remains registered on port 8765

  Scenario: The resident supervisor probes on a 30-second cadence
    Given a supervisor with a healthy running Workout service
    When its resident health monitor runs for two intervals
    Then the monitor waits 30 seconds between health sweeps

  Scenario: An unhealthy Workout service recovers under the same supervisor
    Given a supervisor whose running Workout service becomes unhealthy
    When the due recovery attempt succeeds
    Then the service returns to ready without changing its launch generation

  Scenario: Failed recovery retries continue with capped backoff
    Given a Workout service that remains unhealthy through six recovery attempts
    When the supervisor advances through each retry deadline
    Then retry delays increase to a 300-second cap and continue until recovery

  Scenario: Repeated failures surface Attention and recovery clears it
    Given a running Workout service that fails repeatedly
    When the supervisor exposes the repeated failure and then Retry succeeds
    Then the portal shows Attention while failed and clears it after recovery

  Scenario: Portal Retry uses the existing supervisor API and state
    Given a Workout service is running under the portal supervisor
    When I submit Retry through the authorized portal API
    Then the same supervisor updates the service state in its current generation

  Scenario: An unowned listener is not terminated during Workout reclaim
    Given an unverified process is listening on the Workout port
    When the supervisor attempts a managed-only port reclaim
    Then it reports an ownership failure and leaves the listener untouched

  Scenario: The resident monitor shares the sole process owner
    Given the resident portal is started with one supervisor instance
    When background work is registered
    Then health monitoring is bound to that same supervisor instance