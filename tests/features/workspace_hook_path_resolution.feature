Feature: Workspace hook installation uses the canonical checkout path

  Scenario: A valid Workspace checkout configures all five intended repositories
    Given a valid Workspace checkout with the canonical hook directory and five intended repositories
    When the hook installer runs for a valid checkout
    Then all five repositories use the existing canonical hook directory under that checkout

  Scenario: A missing or invalid canonical hook directory fails before configuration changes
    Given the canonical hook directory is missing or is not a directory
    When the hook installer runs with an invalid canonical directory
    Then it fails without changing any repository hook configuration

  Scenario: Installed pre-commit hooks retain worktree, secret, and private-data checks
    Given the canonical pre-commit hook is installed in the five intended repositories
    When the installed pre-commit hook processes staged violations
    Then each existing safeguard rejects its matching violation