Feature: Versioned FR acceptance criteria amendments
  Scenario: Invalid amendments are rejected without mutation
    Given missing approval, malformed criteria, a stale expected version, or an inactive/terminal FR
    When an amendment is attempted
    Then it is rejected and neither the current criteria nor version history changes

  Scenario: Successful approval stores an immutable current criteria version
    Given an active FR with current G/W/T criteria
    When intake records scope-amendment approval and the CLI receives the full proposed criteria, rationale, and matching expected version
    Then it atomically stores a new immutable criteria version and makes it current

  Scenario: Successful amendments reset active FRs and preserve history
    Given a successful amendment at any active pre-merge state
    When it is committed
    Then the FR returns to TRIAGED; its branch, PR, old events, artifacts, and previous criteria remain recorded; and fresh scope approval is required before BRANCHED

  Scenario: Downstream gates require evidence for the current criteria version
    Given a new current criteria version
    When a downstream gate is checked
    Then evidence tied only to an earlier criteria version cannot pass it; current-version evidence is required for implementation/QA, architecture review, and automated review

  Scenario: Existing intake and correction-only repair behavior remains unchanged
    Given a new FR or a correction to existing criteria
    When existing intake or repair commands are used
    Then their current behavior and guards remain unchanged

  Scenario: Terminal and post-merge FRs cannot be amended
    Given an FR is CLOSED, ARCHIVED, MERGED, SOAKING, or SIGNED_OFF
    When amendment is attempted
    Then the operation is refused without mutation

  Scenario: Host-limited QA evidence advances without claiming an agent behavior pass
    Given a current criteria version has passing implementation evidence
    When QA records a host limitation for an agent-only criterion
    Then the ledger accepts the limited QA outcome without labeling it PASS

  Scenario: Limited QA is blocked without a structured limitation artifact
    Given a current criteria version has passing implementation evidence
    When QA records a limited result without its limitation artifact
    Then the ledger blocks Functional QA advancement

  Scenario: Limited QA cannot mark a deterministic criterion unverified
    Given a current criteria version has passing implementation evidence
    When QA marks a deterministic criterion as host-unverified
    Then the ledger blocks Functional QA advancement

  Scenario: Limited QA cannot read evidence outside the FR proof worktree
    Given a current criteria version has passing implementation evidence
    When QA links structured limitation evidence outside the FR proof worktree
    Then the ledger blocks Functional QA advancement

  Scenario: Limited QA cannot bypass failed security or functional checks
    Given a current criteria version has passing implementation evidence
    When the limitation artifact reports a failed security or other check
    Then the ledger blocks Functional QA advancement for failed checks

  Scenario: Limited QA requires well-formed current evidence identity
    Given a current criteria version has passing implementation evidence
    When the limitation artifact has mismatched identity or malformed classification
    Then the ledger blocks Functional QA advancement for invalid evidence

  Scenario: Limited QA rejects malformed schema versions and limitation reasons
    Given a current criteria version has passing implementation evidence
    When the limitation artifact has a boolean schema version or mismatched reason
    Then the ledger blocks Functional QA advancement for malformed proof