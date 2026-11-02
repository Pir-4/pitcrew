# clients/

One small client per external service, with only the calls Pitcrew needs, and the web links
to their pages.

| Module | Service |
|--------|---------|
| `base.py` | `BaseClient`: the `httpx2` connection pool, timeout, `close`, error mapping, a log line per call |
| `testops.py` | Allure TestOps REST API (`Api-Token`), ADR 0001 |
| `gitlab.py` | GitLab REST API (`PRIVATE-TOKEN`); `InputValue`, the value of a pipeline's `spec:inputs` input, which the Team config's `rerun.pipeline_inputs` takes |
| `slack.py` | Slack incoming webhooks: `SlackClient.post(webhook_variable, message)` of a `SlackMessage` (the notification text and the Block Kit blocks) |
| `links.py` | `WebLinks`: the web page links to a GitLab pipeline, a TestOps launch, a test result in a launch and a test case search, from the service settings |
| `exceptions.py` | `ClientException` and the statuses a caller tells apart |

## Rules

- A client subclasses `BaseClient` and calls `_get` / `_post` / `_patch` (JSON answers) or
  `_send` (any answer), never `self._http` directly: the base turns `401` / `403` / `404` into
  the exceptions of `exceptions.py`, any other error status into `ClientException`, and logs
  every call.
- The constructor takes the client's own settings group (`AllureSettings`, `GitLabSettings`),
  never the whole `Settings`, plus an optional `transport` for the tests. Two take `Settings`
  on purpose: `SlackClient`, which reads every webhook the Team configs name through
  `Settings.secret` up front, so that a missing one stops the startup; `WebLinks`, which
  reads the web URLs of several services.
- A client imports nothing from the Team config (`config/team.py`): a type of its API that a
  Team config holds is defined in the client, and `team.py` imports it from there.
- A method returns typed data (a frozen dataclass such as `TestResult`, `Job`), never raw JSON.
- A web page link is built only in `WebLinks` (`pipeline`, `launch`, `test_result`,
  `test_cases`), from the settings, without a request; a client has no link method. A new
  link is a new method there.
- A URL holding a secret is masked by overriding `_error_url`. A Slack webhook is named by the
  variable the Team config gives, read through `Settings.secret`; errors show the variable,
  never the URL.
- A GitLab pipeline's `spec:inputs` go as `inputs`, not as variables.
- Clients and `WebLinks` are created in `main.lifespan` (clients closed on shutdown) and
  reached through `api/dependencies.py`, which hands them to the Steps in `StepDependencies`.

## Tests

A client is replaced in the tests by one built on a faked transport (`tests/support/fakes.py`)
that answers from a recorded night, `tests/data/scenarios/<night>/`; recording a new night:
`tests/data/AGENTS.md`. What only a client does (paging, query building) and the links of `WebLinks` are tested in
`tests/test_clients/`.
