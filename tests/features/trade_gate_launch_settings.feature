Feature: Scope Trade Gate worker settings to SigmaCapital
  Scenario: A fresh SigmaCapital launch passes worker settings and keeps health available
    Given a disposable SigmaCapital project root
    When the real Trade Gate launcher starts a fresh child
    Then the child inherits SigmaCapital worker settings and Scheduler Health responds

  Scenario: A different ProjectRoot does not receive SigmaCapital worker settings
    Given a disposable non-SigmaCapital project root
    When the real Trade Gate launcher starts a fresh child
    Then the child does not inherit SigmaCapital worker settings

  Scenario: Worker settings do not leak to a later project launched in the same shell
    Given SigmaCapital and another project root are prepared
    When both launch sequentially from one PowerShell process
    Then the later child and launcher shell do not retain the SigmaCapital worker settings