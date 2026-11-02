# Tests

How the tests of Pitcrew are laid out and written. `/code-review` holds new tests to these
rules.

## Layout by seam

A test crosses the highest interface that holds the behaviour it checks, and lives in the folder
of that seam. A folder of tests is named `test_<what it tests>`, after the source package or
the seam; a folder of test code or data is named so that it cannot be read as tests
(`support/`, `data/`):

| Folder | Seam | What goes there |
|--------|------|-----------------|
| `test_run_chain/` | HTTP: `POST /triggers`, `GET /run-chains/{trace_id}` with faked TestOps, GitLab and Slack, driven by the `pitcrew` driver (see `test_run_chain/AGENTS.md`) | One module per concern: `test_triggers.py` (a trigger accepted or rejected: one table of the rejected ones), `test_night_run.py`, `test_night_rerun.py` (what each Step does), `test_run_chain_status.py` (the shape of what `GET /run-chains` shows, a failed Step's `failed` and `failure_reason` included; what a Step's failure records, masked, and its resume clearing it are tested in that Step's module), `test_logging.py` (what the logging of the whole Run chain holds: the trace id, the request id, masked secrets, a Step's failure logged once by `BaseStep` with its context and traceback); a log line of one Step or one trigger is tested in that Step's or the triggers' module |
| `test_steps/` | The rule functions, `conclusion_message` and the `Publisher` of `src/pitcrew/steps/`, called directly | `test_outcome.py` (when a Nightly run or Rerun is broken, and why), `test_error_groups.py` (which Failed tests form an Error group, and the order of the groups), `test_conclusion.py` (the message `conclusion_message` builds for a Run chain held in memory, its `Run` rows judged with their stored outcomes and reasons, and the `links` fixture; no client at all), `test_publisher.py` (what the `Publisher` posts to the faked Slack and records on a chain held in memory: posted once, already posted, and nothing for a Team without the feature or a Slack channel) |
| `test_db/` | A transition of a model of `src/pitcrew/db/models/` on an instance held in memory, or a rule the DB itself holds (a unique constraint) saved through `Repositories` into a fresh SQLite file migrated as at startup; only where HTTP cannot show it | `test_run_chain.py` (`RunChain`: a Rerun launch accepted again keeps the first), `test_posts.py` (the store refuses a second post of the same chain, kind and key), `test_status_columns.py` (the store refuses a status none of its enum's values); `conftest.py` holds `session_factory` (the sessions of a fresh migrated SQLite file) |
| `test_clients/` | A client of `src/pitcrew/clients/` or `WebLinks`, called directly | `test_links.py` (the test-cases link, checked once in full) |
| `test_config/` | `Settings`, the Team configs and the app's startup | `test_settings.py` (where settings come from), `test_team_config.py` (how a Team config is read), `test_startup.py` (what stops the service from starting: one table) |
| `support/` | none: shared test code, see `support/AGENTS.md` | Fakes, constants, helpers |
| `data/` | none: recorded nights, Team configs and expected values, see `data/AGENTS.md` | `scenarios/`, the nights of the Run chain; `team_configs/`, the Team config variants; `conclusions.py`, the expected Slack posts |
| `test_agent/` | A class of `src/pitcrew/agent/`, called directly, with a fake `AgentRunner` for the SDK | `test_environment.py` (the whole env Claude Code gets from `AgentEnvironment.for_model`), `test_agent.py` (what `Agent.run` gives Claude Code on a plain directory, the prompt with its secrets masked and its test data as is, how a task ends as its `AgentResult`, what it logs), `test_working_copy.py` (`WorkingCopies` against `origin`, a local bare repo: the ref, the files left out, the clean-up, the token kept out) |
| root | a module of its own | `test_main.py` (`/health`), `test_cli.py` (`pitcrew agent-smoke`: what it asks, in which Working copy, what it prints and returns) |

A rule is tested at its function, as a table of cases; the Run chain is tested through HTTP,
for its wiring only (that a Step applies the rule and acts on its answer), never for every case
of a rule. A new test goes into the module of its seam; a new seam (a rule function, a class
tested directly) gets a folder of tests mirroring its source package (`test_steps/`, `test_clients/`).

A Step (one class per Step, built per execution by its one entry point `BaseStep.run`, the
shared helpers in `BaseStep`: `src/pitcrew/steps/AGENTS.md`) is tested only end to end, through
`test_run_chain/`: never by building a Step, calling `run` or a helper of `BaseStep` directly.
How a Step is split into classes and helpers is not a behaviour, so a change of its shape
passes the Run chain suite unchanged.

## One test, one behaviour

- One test function per behaviour, named after it. Cases of the same behaviour are
  `pytest.param(..., id="...")` rows of one parametrised test, the id reading as the case. A
  different action or a different assertion is a different test.
- The body is three blocks, given / when / then, separated by blank lines.
- A docstring only for a reason the code cannot show; an assert message only where pytest
  cannot show the meaning itself.

## Expected values

- The expected value is a literal or a constant of `data/`, written by hand (or recorded and
  read line by line), never built by a helper that rebuilds what production builds: such a
  helper agrees with the code by construction.
- To make the actual value readable, decode the actual, never encode the expected:
  `post_text` turns a posted Block Kit message into its lines and the test-cases search into
  its AQL; the expected post stays the text a person reads.
- A Conclusion is checked as a whole post against its constant, at `test_steps/` and end to end
  alike: one constant serves both levels.

## Rule tables

- A case's inputs are literals next to its expected answer: a reader never opens a recording
  to understand a case.
- An error text in a case is copied from a recorded result and cut to what the rule reads, with
  a comment naming its launch (and result); a text altered for the case says how.
- A look-alike the rule must not match (ADR 0004) is a case of its own.

## Names

- No leading underscore on a helper, fixture, constant or class of the tests.
- No function, method, fixture or constant of the tests starts with `test` unless it is a test
  (pytest would collect it from a test module): it is named after what it gives
  (`link_to_test_cases`, not `test_cases_url`). A data field or property that mirrors a name
  of the domain or of production code keeps it (`Run.test_plan_id`): pytest collects no
  attribute.

## Fixtures

- A fixture lives in the nearest `conftest.py` that covers all its users; one used by a single
  module lives in that module.
- A fixture gives one thing and is named by it (a noun: `service_env`, `testops`, `logs`). It
  asserts nothing and is never autouse: a test's dependencies are visible in its signature.
- The root `conftest.py` holds `logs` (the log output, parsed), `service_env` (the
  service's environment: SQLite in `tmp_path`, the repo's base config with the `gateway`
  variant, the test tokens), `links` (`WebLinks` of `service_env`),
  `slack` (Slack faked, what was posted), `agent_env` (`service_env` with LiteLLM, the
  models, the Agent's limits and `work_dir`, run from `tmp_path`), `work_dir` and `origin`
  (`qa_automation` on GitLab: a local bare repo the clone URL resolves to); `test_run_chain/conftest.py` holds the other fakes
  (`testops`, `gitlab`), `load_scenario` (loads a night into both fakes, gives its ids) and
  `start_pitcrew` (starts the app with the fakes in place and a named Team config variant as
  the config of a Team, Gateway by default, gives its driver, `Pitcrew`), `pitcrew`
  (`start_pitcrew()` with the `gateway` variant) and `client` (the raw `TestClient` of
  `pitcrew`, for the tests of HTTP itself).
- A parameter of a fixture is passed through a factory fixture the test calls once, in its
  given block: `night = load_scenario("green_night")`,
  `pitcrew = start_pitcrew(config="gateway_without_rerun")`.

## Team configs

- The tests read the repo's real `config/base.yaml`, so a drift from production shows. A Run
  chain test picks a Gateway variant of `data/team_configs/` by name through
  `start_pitcrew` (`team=` names another Team to give it to, for a test of a Team that exists
  only as a Team config); it never writes or edits YAML (no `replace`, no appended overrides,
  no inline config).
- Only the tests of Team config validation (`test_config/`) hold their YAML inline, through
  `tests.support.config.use_config`: there the YAML is the input under test.
- A test that needs a `TeamConfig` value (a Step's part) takes a variant through
  `tests.support.config.load_team_config`, never `TeamConfig.load` on a variant: a variant
  names no Team.
- A Team config's file name is never spelled by hand: `team_config_file(team)` names it.
