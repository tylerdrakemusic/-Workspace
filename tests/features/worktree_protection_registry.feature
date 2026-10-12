Feature: Worktree cleanup protection registry
  Scenario: Hygiene identifies a registered worktree as protected
    Given a repository contains a registered worktree candidate
    When the generic worktree protection command checks the candidate
    Then the candidate is reported protected without disclosing worktree contents