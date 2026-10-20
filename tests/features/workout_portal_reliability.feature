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

  Scenario: The current-user logon task starts one supervisor without credentials
    Given a Workspace root and current-user SID
    When I build the current-user logon task plan
    Then the task invokes the existing supervisor dispatcher once
    And the task uses the current user's interactive least-privilege principal
    And duplicate task instances are ignored without stored credentials

  Scenario: The Windows installer can consume the portable plan on any CI platform
    Given a Workspace root and current-user SID
    When I request the task plan from the supervisor CLI
    Then the CLI returns the same current-user logon contract

  Scenario: A task plan from a feature worktree targets the primary checkout
    Given a Workspace feature-worktree root and current-user SID
    When I build the current-user logon task plan
    Then the task targets the primary Workspace checkout, not the disposable worktree

  Scenario: An exact existing logon task matches its identity contract
    Given the intended current-user logon task
    When I verify its exported scheduled-task definition
    Then the task identity matches the intended plan

  Scenario: A disabled logon task does not satisfy the startup contract
    Given the intended current-user logon task
    When the exported task is disabled
    Then the task identity does not match the intended plan

  Scenario: Registering an exact existing task is a no-op
    Given the intended current-user logon task
    When the existing task is evaluated for registration
    Then the installer decision is "noop"

  Scenario: Unregistering an exact existing task is allowed
    Given the intended current-user logon task
    When the existing task is evaluated for unregistration
    Then the installer decision is "unregister"

  Scenario: A missing task is registered or left absent according to the operation
    Given a planned current-user logon task
    When a missing task is evaluated for registration
    Then the installer decision is "register"
    When a missing task is evaluated for unregistration
    Then the installer decision is "noop"

  Scenario Outline: A changed logon task identity is rejected
    Given the intended current-user logon task
    When the exported task has a different <identity>
    Then the task identity does not match the intended plan

    Examples:
      | identity                  |
      | action                    |
      | principal                 |
      | trigger                   |
      | multiple-instance policy  |

  Scenario Outline: A changed task cannot be registered over or removed
    Given the intended current-user logon task
    When an existing task has a different <identity> during <operation>
    Then the installer rejects the existing task without changing its definition

    Examples:
      | identity                 | operation      |
      | action                   | registration   |
      | principal                | registration   |
      | trigger                  | registration   |
      | multiple-instance policy | registration   |
      | action                   | unregistration |
      | principal                | unregistration |
      | trigger                  | unregistration |
      | multiple-instance policy | unregistration |

  Scenario: Repeated automatic dispatch does not start a second supervisor
    Given a logon dispatcher whose resident supervisor is inactive
    When the same automatic start is dispatched twice
    Then the duplicate invocation does not start or focus another process