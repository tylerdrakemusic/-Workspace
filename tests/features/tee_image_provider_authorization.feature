Feature: Authorized provider routing for tee artwork

  Scenario: Default tee generation attempts only the allowlisted Fal Krea route
    Given tee generation starts with OpenAI disabled and only Fal Krea authorized
    When the tee cascade generates an image
    Then only the Fal Krea route is attempted and its provider and model are returned

  Scenario: Unverified Pollinations is skipped after Fal Krea fails
    Given Fal Krea is the only authorized route and Pollinations remains unverified
    When Fal Krea fails during tee generation
    Then Pollinations is skipped and the error reports no authorized route remains

  Scenario: OpenAI requires both its toggle and an authorized exact route
    Given the OpenAI toggle is enabled but its exact route is not allowlisted
    When tee generation runs before and after that exact route is allowlisted
    Then OpenAI is skipped first and eligible in provider order only after allowlisting

  Scenario: A one-shot 512 square probe stays in temporary storage
    Given the Fal Krea route is mocked and temporary output is available
    When the route is called once at 512 by 512 and then tested for failure
    Then successful output stays temporary and the failed request is not retried